#!/usr/bin/env python3
"""
pokedex_retro_view.py - Authentic In-Game GBA Pokédex View
===========================================================
Replicates the exact GBA Pokédex layout from Moemon Quetzal / Pokémon Emerald:
- Clean white tiled grid background.
- Top-center red rounded badge with white bold text "POKÉDEX".
- Left pane: Vertical scrollable list with 4-digit numbers (#0001 - #1025),
  Pokéball icons for caught, species names for seen, "-----------" for unseen.
- Center pane: Large centered pixel art sprite with rolling vertical carousel
  previewing previous and next Pokémon.
- Right top pane: "NATIONAL" card with Seen and Own counts from the save file.
- Right bottom pane: Base stats horizontal bars (HP, AT, DE, SA, SD, SP).
"""

import os
import sqlite3
import subprocess
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem, QFrame,
    QScrollArea, QSizePolicy, QGraphicsOpacityEffect, QStackedWidget
)
from PySide6.QtGui import (
    QPainter, QPixmap, QColor, QFont, QPen, QBrush, QImage,
    QCursor, QIcon
)
from PySide6.QtCore import (
    Qt, QRectF, QPointF, QSize, Signal
)

import quetzal_save_reader

PROJECT_DIR = "/home/vibecoder/Projects"
DB_PATH = os.path.join(PROJECT_DIR, "quetzal_database.db")
DEFAULT_SAV_PATH = "/home/vibecoder/Games/Console Games/GBA/Moemon Quetzal.sav"
SPRITES_DIR = os.path.join(PROJECT_DIR, "assets", "sprites")
SILHOUETTES_DIR = os.path.join(PROJECT_DIR, "assets", "silhouettes")
SFX_DIR = os.path.join(PROJECT_DIR, "assets", "sfx")

# Audio SFX helper
def play_sfx(name: str):
    """Play sound effect non-blockingly using paplay or aplay."""
    wav = os.path.join(SFX_DIR, name)
    if os.path.exists(wav):
        cmd = ["paplay", wav] if subprocess.run(["which", "paplay"], capture_output=True).returncode == 0 else ["aplay", "-q", wav]
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

# Cached Pokéball Icon Generator
_CACHED_POKEBALL_ICON: Optional[QIcon] = None

def get_pokeball_icon() -> QIcon:
    """Generate crisp GBA Pokéball icon for caught entries."""
    global _CACHED_POKEBALL_ICON
    if _CACHED_POKEBALL_ICON is not None:
        return _CACHED_POKEBALL_ICON

    img = QImage(24, 24, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    painter = QPainter(img)
    painter.setRenderHint(QPainter.Antialiasing, True)

    rect = QRectF(3, 3, 18, 18)
    # Red top half
    painter.setPen(QPen(QColor("#0f172a"), 1.4))
    painter.setBrush(QColor("#ef4444"))
    painter.drawChord(rect, 0 * 16, 180 * 16)

    # White bottom half
    painter.setBrush(QColor("#ffffff"))
    painter.drawChord(rect, 180 * 16, 180 * 16)

    # Dividing band
    painter.drawLine(rect.left(), rect.center().y(), rect.right(), rect.center().y())

    # Center button
    painter.setBrush(QColor("#ffffff"))
    painter.setPen(QPen(QColor("#0f172a"), 1.4))
    painter.drawEllipse(rect.center(), 3.5, 3.5)

    painter.setBrush(QColor("#94a3b8"))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(rect.center(), 1.6, 1.6)

    painter.end()
    _CACHED_POKEBALL_ICON = QIcon(QPixmap.fromImage(img))
    return _CACHED_POKEBALL_ICON


# ---------------------------------------------------------------------
# TYPE COLORS, METHOD FORMATTING & RETRO CARDS
# ---------------------------------------------------------------------
TYPE_COLORS = {
    "Normal": "#94a3b8", "Fire": "#ef4444", "Water": "#3b82f6",
    "Grass": "#22c55e", "Electric": "#eab308", "Ice": "#06b6d4",
    "Fighting": "#b91c1c", "Poison": "#a855f7", "Ground": "#d97706",
    "Flying": "#818cf8", "Psychic": "#ec4899", "Bug": "#84cc16",
    "Rock": "#78716c", "Ghost": "#6366f1", "Dragon": "#4f46e5",
    "Steel": "#64748b", "Dark": "#334155", "Fairy": "#f472b6"
}

def get_type_color(type_name: Optional[str]) -> str:
    if not type_name:
        return "#64748b"
    return TYPE_COLORS.get(type_name.capitalize(), "#64748b")

SPECIAL_GIFTS_DATABASE: Dict[int, str] = {
    1: "Starter Gift: Available in early routes & Professor Birch's expansion.",
    4: "Starter Gift: Available on Route 116 & Professor Birch's expansion.",
    7: "Starter Gift: Available in Professor Birch's expansion.",
    133: "Gift: Prize Pokémon obtainable at Mauville / Celadon Game Corner.",
    137: "Gift: Prize Pokémon available at Mauville Game Corner.",
    138: "Fossil: Revive Helix Fossil at Devon Corporation (Rustboro City 2F).",
    140: "Fossil: Revive Dome Fossil at Devon Corporation (Rustboro City 2F).",
    142: "Fossil: Revive Old Amber at Devon Corporation (Rustboro City 2F).",
    152: "Starter Gift: Received from Prof. Birch's Lab in Littleroot Town after completing Hoenn Pokédex.",
    155: "Starter Gift: Received from Prof. Birch's Lab in Littleroot Town after completing Hoenn Pokédex.",
    158: "Starter Gift: Received from Prof. Birch's Lab in Littleroot Town after completing Hoenn Pokédex.",
    175: "Gift Egg: Received from Traveling NPC / Pokémon Day Care.",
    252: "Starter Choice: Pick Treecko from Prof. Birch's bag on Route 101.",
    255: "Starter Choice: Pick Torchic from Prof. Birch's bag on Route 101.",
    258: "Starter Choice: Pick Mudkip from Prof. Birch's bag on Route 101.",
    345: "Fossil: Revive Root Fossil at Devon Corporation (Rustboro City 2F).",
    347: "Fossil: Revive Claw Fossil at Devon Corporation (Rustboro City 2F).",
    351: "Special Gift: Awarded by Weather Institute Scientist (Route 119) after defeating Team Aqua/Magma.",
    360: "Gift Egg: Received from the elderly lady near Lavaridge Town hot springs.",
    374: "Special Gift: Pokéball waiting on the desk in Steven's House (Mossdeep City) post-game.",
    408: "Fossil: Revive Skull Fossil at Devon Corporation (Rustboro City 2F).",
    410: "Fossil: Revive Armor Fossil at Devon Corporation (Rustboro City 2F).",
    564: "Fossil: Revive Cover Fossil at Devon Corporation (Rustboro City 2F).",
    566: "Fossil: Revive Plume Fossil at Devon Corporation (Rustboro City 2F).",
    696: "Fossil: Revive Jaw Fossil at Devon Corporation (Rustboro City 2F).",
    698: "Fossil: Revive Sail Fossil at Devon Corporation (Rustboro City 2F)."
}

def format_evolution_method(method: str) -> str:
    method_map = {
        "Method 26": "Use Dawn Stone (Male)",
        "Method 27": "Use Dawn Stone (Female)",
        "Method 28": "Level 50 in Rain",
        "Method 29": "Level Up with Remoraid / Trade",
        "Method 30": "Level 32 with Dark-type in Party",
        "Method 31": "Trade with Shelmet/Karrablast",
        "Method 33": "Level 30 (Amped Nature)",
        "Method 34": "Level 30 (Low Key Nature)",
        "Method 41": "Use Linking Cord / Item",
        "Method 42": "Level 50 in Rain",
        "Method 43": "Level 25",
        "Method 44": "Learn Hyper Drill",
        "Method 45": "Level 36",
        "Method 46": "Level 19",
    }
    return method_map.get(method, method)

def get_species_form_name(species_id: int, base_id: int) -> str:
    if species_id == base_id:
        return "Standard"
    if 949 <= species_id <= 966:
        return "Alolan"
    if 967 <= species_id <= 985:
        return "Galarian"
    if 1223 <= species_id <= 1239:
        return "Hisuian"
    if 1363 <= species_id <= 1369:
        return "Paldean"
    if 899 <= species_id <= 948:
        return "Mega"
    return "Alternate"


class EvoNodeCard(QFrame):
    """Interactive retro Pokémon card in evolution chain."""
    def __init__(self, species_id: int, nat: int, name: str, type1: Optional[str], type2: Optional[str],
                 is_current: bool, is_seen: bool, pixmap: Optional[QPixmap],
                 form_name: str = "", on_click=None, parent=None):
        super().__init__(parent)
        self.nat = nat
        self.on_click = on_click
        self.setCursor(QCursor(Qt.PointingHandCursor))

        if is_current:
            self.setStyleSheet("""
                QFrame {
                    background-color: #fef2f2;
                    border: 2px solid #ef4444;
                    border-radius: 6px;
                }
                QFrame:hover {
                    background-color: #fee2e2;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: #ffffff;
                    border: 2px solid #cbd5e1;
                    border-radius: 6px;
                }
                QFrame:hover {
                    background-color: #f1f5f9;
                    border-color: #94a3b8;
                }
            """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(8)

        # Sprite
        sp_lbl = QLabel()
        sp_lbl.setFixedSize(36, 36)
        sp_lbl.setAlignment(Qt.AlignCenter)
        if pixmap and not pixmap.isNull():
            sp_lbl.setPixmap(pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.FastTransformation))
        else:
            sp_lbl.setText("❓")
        layout.addWidget(sp_lbl)

        # Info VBox
        vbox = QVBoxLayout()
        vbox.setSpacing(2)
        vbox.setContentsMargins(0, 0, 0, 0)

        title_row = QHBoxLayout()
        title_row.setSpacing(4)
        nat_str = f"#{nat:04d}"

        name_lbl = QLabel(f"{nat_str} {name.upper()}")
        name_lbl.setStyleSheet(f"""
            color: {'#b91c1c' if is_current else '#0f172a'};
            font-family: 'JetBrainsMono Nerd Font', monospace;
            font-size: 11px;
            font-weight: 900;
        """)
        title_row.addWidget(name_lbl)

        if form_name and form_name != "Standard":
            f_lbl = QLabel(f"[{form_name}]")
            f_lbl.setStyleSheet("""
                color: #0284c7;
                font-family: 'JetBrainsMono Nerd Font', monospace;
                font-size: 9px;
                font-weight: bold;
            """)
            title_row.addWidget(f_lbl)

        title_row.addStretch()

        if is_current:
            cur_badge = QLabel("★ ACTIVE")
            cur_badge.setStyleSheet("""
                color: #ef4444;
                font-family: 'JetBrainsMono Nerd Font', monospace;
                font-size: 9px;
                font-weight: 900;
            """)
            title_row.addWidget(cur_badge)

        vbox.addLayout(title_row)

        # Types row
        types_h = QHBoxLayout()
        types_h.setSpacing(4)
        for t in (type1, type2):
            if t and t != "None" and is_seen:
                t_badge = QLabel(t.upper())
                t_badge.setStyleSheet(f"""
                    background-color: {get_type_color(t)};
                    color: #ffffff;
                    border-radius: 3px;
                    font-family: 'JetBrainsMono Nerd Font', monospace;
                    font-size: 8px;
                    font-weight: 900;
                    padding: 1px 5px;
                """)
                types_h.addWidget(t_badge)
        types_h.addStretch()
        vbox.addLayout(types_h)

        layout.addLayout(vbox, 1)

    def mousePressEvent(self, event):
        if self.on_click:
            self.on_click(self.nat)
        super().mousePressEvent(event)


def create_evo_arrow(method_text: str, is_branch: bool = False) -> QWidget:
    """Crisp GBA method arrow."""
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 1, 0, 1)
    h.setSpacing(4)
    h.setAlignment(Qt.AlignCenter)

    arrow_sym = "┡──▶ [ " if is_branch else "▼ ──[ "
    lbl = QLabel(f"{arrow_sym}{method_text} ]──▶")
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet("""
        color: #047857;
        background-color: #ecfdf5;
        border: 1px solid #10b981;
        border-radius: 4px;
        font-family: 'JetBrainsMono Nerd Font', monospace;
        font-size: 9px;
        font-weight: bold;
        padding: 2px 6px;
    """)
    h.addWidget(lbl)
    return w


class PokedexRetroView(QWidget):
    """
    Authentic in-game GBA Pokédex screen replicating uploaded_media_1.
    """
    pokemon_selected = Signal(int)  # emits national_dex_num

    def __init__(self, db_path: str = DB_PATH, save_path: str = DEFAULT_SAV_PATH, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.save_path = save_path

        # Pokédex database records indexed by national_dex_num (1..1025)
        self.pokemon_by_nat: Dict[int, Dict[str, Any]] = {}
        self.nat_nums: List[int] = []
        self.seen_species: set = set()
        self.caught_species: set = set()
        self.sp_to_nat: Dict[int, int] = {}
        self.nat_to_base_id: Dict[int, int] = {}

        self.current_nat: int = 1  # Selected national dex number
        self.filter_mode: str = "ALL"  # "ALL", "SEEN", "CAUGHT"
        self.search_query: str = ""

        # Sprite cache
        self.sprite_cache: Dict[int, QPixmap] = {}
        self.silhouette_cache: Dict[int, QPixmap] = {}

        # Right Card Tab state: 0 = STATS, 1 = EVOS, 2 = HOW_TO_GET
        self.current_right_tab: int = 0
        self.all_pokemon_records: Dict[int, Dict[str, Any]] = {}
        self.nat_to_all_sps: Dict[int, List[int]] = defaultdict(list)
        self.evo_forward: Dict[int, List[Tuple[int, str]]] = defaultdict(list)
        self.evo_backward: Dict[int, List[Tuple[int, str]]] = defaultdict(list)
        self.legendaries_list: List[Dict[str, Any]] = []
        self.encounters_by_sp_id: Dict[int, List[Dict[str, Any]]] = defaultdict(list)

        self.init_ui()
        self.load_data()
        if 142 in self.pokemon_by_nat:
            # Default to Aerodactyl (#0142) as shown in reference ground truth
            self.select_pokemon(142)
        elif self.nat_nums:
            self.select_pokemon(self.nat_nums[0])

    def paintEvent(self, event):
        """Draw authentic white tiled grid background."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#f8fafc"))

        # Draw clean 16x16 blueprint grid lines
        painter.setPen(QPen(QColor("#e2e8f0"), 1.0))
        w = self.width()
        h = self.height()
        for x in range(0, w, 16):
            painter.drawLine(x, 0, x, h)
        for y in range(0, h, 16):
            painter.drawLine(0, y, w, y)

    def init_ui(self):
        """Initialize the 3-pane authentic GBA Pokédex layout."""
        self.setFocusPolicy(Qt.StrongFocus)
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 12, 18, 16)
        root_layout.setSpacing(10)

        # -------------------------------------------------------------
        # TOP HEADER: Red rounded pill badge "POKÉDEX"
        # -------------------------------------------------------------
        top_header = QHBoxLayout()
        top_header.setSpacing(12)

        # Quick Search Bar & Filters
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Search # or Pokémon...")
        self.search_edit.setFixedHeight(32)
        self.search_edit.setFixedWidth(240)
        self.search_edit.setStyleSheet("""
            QLineEdit {
                background-color: #ffffff;
                color: #0f172a;
                border: 2px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 10px;
                font-family: 'JetBrainsMono Nerd Font', monospace;
                font-size: 11px;
                font-weight: bold;
            }
            QLineEdit:focus {
                border: 2px solid #ef4444;
            }
        """)
        self.search_edit.textChanged.connect(self.on_search_changed)
        top_header.addWidget(self.search_edit)

        # Filter Chips: [ALL] [SEEN] [OWN]
        self.btn_filter_all = QPushButton("ALL")
        self.btn_filter_seen = QPushButton("SEEN")
        self.btn_filter_own = QPushButton("OWN")

        for btn in (self.btn_filter_all, self.btn_filter_seen, self.btn_filter_own):
            btn.setFixedHeight(30)
            btn.setFixedWidth(64)
            btn.setCursor(QCursor(Qt.PointingHandCursor))

        self.btn_filter_all.clicked.connect(lambda: self.set_filter_mode("ALL"))
        self.btn_filter_seen.clicked.connect(lambda: self.set_filter_mode("SEEN"))
        self.btn_filter_own.clicked.connect(lambda: self.set_filter_mode("CAUGHT"))

        top_header.addWidget(self.btn_filter_all)
        top_header.addWidget(self.btn_filter_seen)
        top_header.addWidget(self.btn_filter_own)
        self._update_filter_button_styles()

        top_header.addStretch(1)

        # Center Red Pill Badge: POKÉDEX
        self.badge_lbl = QLabel("POKÉDEX")
        self.badge_lbl.setAlignment(Qt.AlignCenter)
        self.badge_lbl.setFixedSize(180, 36)
        self.badge_lbl.setStyleSheet("""
            QLabel {
                background-color: #ef3131;
                color: #ffffff;
                border: 2px solid #b91c1c;
                border-radius: 12px;
                font-family: 'JetBrainsMono Nerd Font', monospace;
                font-size: 16px;
                font-weight: 900;
                letter-spacing: 2px;
            }
        """)
        top_header.addWidget(self.badge_lbl)

        top_header.addStretch(1)

        # Right Summary Indicator
        self.region_badge = QLabel("NATIONAL DEX // GEN I - IX")
        self.region_badge.setStyleSheet("""
            color: #475569;
            font-family: 'JetBrainsMono Nerd Font', monospace;
            font-size: 11px;
            font-weight: bold;
        """)
        top_header.addWidget(self.region_badge)

        root_layout.addLayout(top_header)

        # -------------------------------------------------------------
        # 3-PANE MAIN CONTENT AREA
        # -------------------------------------------------------------
        body_layout = QHBoxLayout()
        body_layout.setSpacing(16)

        # -------------------------------------------------------------
        # PANE 1: LEFT VERTICAL LIST (4-digit list #0001 - #1025)
        # -------------------------------------------------------------
        left_box = QFrame()
        left_box.setFixedWidth(330)
        left_box.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 2px solid #293131;
                border-radius: 8px;
            }
        """)
        left_vbox = QVBoxLayout(left_box)
        left_vbox.setContentsMargins(4, 4, 4, 4)
        left_vbox.setSpacing(2)

        self.pokemon_list = QListWidget()
        self.pokemon_list.setFocusPolicy(Qt.StrongFocus)
        self.pokemon_list.setIconSize(QSize(20, 20))
        self.pokemon_list.setStyleSheet("""
            QListWidget {
                background-color: #ffffff;
                border: none;
                font-family: 'JetBrainsMono Nerd Font', monospace;
                font-size: 13px;
                font-weight: bold;
                color: #0f172a;
                outline: none;
            }
            QListWidget::item {
                height: 38px;
                padding-left: 8px;
                padding-right: 8px;
                border-bottom: 1px solid #f1f5f9;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #f1f5f9;
            }
            QListWidget::item:selected {
                background-color: #e2e8f0;
                color: #0f172a;
                border: 2px solid #ef4444;
            }
        """)
        self.pokemon_list.currentItemChanged.connect(self.on_list_item_changed)
        left_vbox.addWidget(self.pokemon_list)

        body_layout.addWidget(left_box)

        # -------------------------------------------------------------
        # PANE 2: CENTER ROLLING CAROUSEL & SPRITE DISPLAY
        # -------------------------------------------------------------
        center_box = QFrame()
        center_box.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.95);
                border: 2px solid #293131;
                border-radius: 8px;
            }
        """)
        center_vbox = QVBoxLayout(center_box)
        center_vbox.setContentsMargins(12, 12, 12, 12)
        center_vbox.setSpacing(8)

        # Top Preview (Previous Pokémon)
        self.prev_container = QFrame()
        self.prev_container.setFixedHeight(64)
        self.prev_container.setCursor(QCursor(Qt.PointingHandCursor))
        self.prev_container.mousePressEvent = lambda e: self.step_selection(-1)
        prev_layout = QHBoxLayout(self.prev_container)
        prev_layout.setContentsMargins(8, 2, 8, 2)
        self.prev_sprite = QLabel()
        self.prev_sprite.setFixedSize(56, 56)
        self.prev_sprite.setAlignment(Qt.AlignCenter)
        self.prev_label = QLabel("▲ Previous Pokémon")
        self.prev_label.setStyleSheet("color: #64748b; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 11px; font-weight: bold;")
        prev_layout.addStretch()
        prev_layout.addWidget(self.prev_sprite)
        prev_layout.addWidget(self.prev_label)
        prev_layout.addStretch()
        center_vbox.addWidget(self.prev_container)

        # Center Main Sprite (Large & Crisp Pixelated)
        self.main_sprite_container = QFrame()
        self.main_sprite_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_sp_layout = QVBoxLayout(self.main_sprite_container)
        main_sp_layout.setAlignment(Qt.AlignCenter)
        main_sp_layout.setContentsMargins(0, 0, 0, 0)

        self.main_sprite = QLabel()
        self.main_sprite.setFixedSize(220, 200)
        self.main_sprite.setAlignment(Qt.AlignCenter)
        main_sp_layout.addWidget(self.main_sprite)

        # Species Title & Number
        self.main_name_lbl = QLabel("0142 AERODACTYL")
        self.main_name_lbl.setAlignment(Qt.AlignCenter)
        self.main_name_lbl.setStyleSheet("""
            color: #0f172a;
            font-family: 'JetBrainsMono Nerd Font', monospace;
            font-size: 20px;
            font-weight: 900;
            letter-spacing: 1.5px;
        """)
        main_sp_layout.addWidget(self.main_name_lbl)

        # Types Row
        self.types_layout = QHBoxLayout()
        self.types_layout.setAlignment(Qt.AlignCenter)
        self.types_layout.setSpacing(6)
        main_sp_layout.addLayout(self.types_layout)

        # Additional quick stats: Abilities & Catch Rate
        self.extra_info_lbl = QLabel("Abilities: Rock Head / Pressure • Catch Rate: 45")
        self.extra_info_lbl.setAlignment(Qt.AlignCenter)
        self.extra_info_lbl.setStyleSheet("color: #475569; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 11px; font-weight: bold;")
        main_sp_layout.addWidget(self.extra_info_lbl)

        center_vbox.addWidget(self.main_sprite_container, 1)

        # Bottom Preview (Next Pokémon)
        self.next_container = QFrame()
        self.next_container.setFixedHeight(64)
        self.next_container.setCursor(QCursor(Qt.PointingHandCursor))
        self.next_container.mousePressEvent = lambda e: self.step_selection(1)
        next_layout = QHBoxLayout(self.next_container)
        next_layout.setContentsMargins(8, 2, 8, 2)
        self.next_sprite = QLabel()
        self.next_sprite.setFixedSize(56, 56)
        self.next_sprite.setAlignment(Qt.AlignCenter)
        self.next_label = QLabel("▼ Next Pokémon")
        self.next_label.setStyleSheet("color: #64748b; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 11px; font-weight: bold;")
        next_layout.addStretch()
        next_layout.addWidget(self.next_sprite)
        next_layout.addWidget(self.next_label)
        next_layout.addStretch()
        center_vbox.addWidget(self.next_container)

        body_layout.addWidget(center_box, 1)

        # -------------------------------------------------------------
        # PANE 3: RIGHT STACK (NATIONAL, TABS, STATS/EVOS/HOW-TO-GET)
        # -------------------------------------------------------------
        right_box = QVBoxLayout()
        right_box.setSpacing(10)

        # CARD 1: NATIONAL DEX PROGRESS
        self.card_national = QFrame()
        self.card_national.setFixedWidth(310)
        self.card_national.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 2px solid #293131;
                border-radius: 8px;
            }
        """)
        cn_layout = QVBoxLayout(self.card_national)
        cn_layout.setContentsMargins(0, 0, 0, 10)
        cn_layout.setSpacing(6)

        # Red top header banner
        banner = QLabel("NATIONAL")
        banner.setAlignment(Qt.AlignCenter)
        banner.setFixedHeight(30)
        banner.setStyleSheet("""
            background-color: #ef3131;
            color: #ffffff;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            border-bottom: 2px solid #b91c1c;
            font-family: 'JetBrainsMono Nerd Font', monospace;
            font-size: 13px;
            font-weight: 900;
            letter-spacing: 2px;
        """)
        cn_layout.addWidget(banner)

        # Seen count row
        seen_row = QHBoxLayout()
        seen_row.setContentsMargins(18, 6, 18, 0)
        lbl_seen_t = QLabel("SEEN")
        lbl_seen_t.setStyleSheet("color: #0f172a; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 14px; font-weight: 900;")
        self.lbl_seen_val = QLabel("0")
        self.lbl_seen_val.setStyleSheet("color: #0f172a; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 16px; font-weight: 900;")
        seen_row.addWidget(lbl_seen_t)
        seen_row.addStretch()
        seen_row.addWidget(self.lbl_seen_val)
        cn_layout.addLayout(seen_row)

        # Divider line
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet("background-color: #ef3131; max-height: 2px; margin: 4px 18px;")
        cn_layout.addWidget(div)

        # Own count row
        own_row = QHBoxLayout()
        own_row.setContentsMargins(18, 0, 18, 4)
        lbl_own_t = QLabel("OWN")
        lbl_own_t.setStyleSheet("color: #0f172a; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 14px; font-weight: 900;")
        self.lbl_own_val = QLabel("0")
        self.lbl_own_val.setStyleSheet("color: #ef3131; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 16px; font-weight: 900;")
        own_row.addWidget(lbl_own_t)
        own_row.addStretch()
        own_row.addWidget(self.lbl_own_val)
        cn_layout.addLayout(own_row)

        # Completion ratio label
        self.lbl_completion = QLabel("0.0% Complete")
        self.lbl_completion.setAlignment(Qt.AlignCenter)
        self.lbl_completion.setStyleSheet("color: #64748b; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 11px; font-weight: bold;")
        cn_layout.addWidget(self.lbl_completion)

        right_box.addWidget(self.card_national)

        # -------------------------------------------------------------
        # RETRO SEGMENTED PILL TAB BAR: [ STATS ] [ EVOS ] [ HOW TO GET ]
        # -------------------------------------------------------------
        self.tab_bar_frame = QFrame()
        self.tab_bar_frame.setFixedWidth(310)
        self.tab_bar_frame.setStyleSheet("""
            QFrame {
                background-color: #e2e8f0;
                border: 2px solid #293131;
                border-radius: 8px;
            }
        """)
        tab_h = QHBoxLayout(self.tab_bar_frame)
        tab_h.setContentsMargins(4, 4, 4, 4)
        tab_h.setSpacing(4)

        self.tab_stats_btn = QPushButton("📊 STATS")
        self.tab_evos_btn = QPushButton("🧬 EVOS & PATHS")
        self.tab_how_to_get_btn = QPushButton("📍 HOW TO GET")

        for btn in (self.tab_stats_btn, self.tab_evos_btn, self.tab_how_to_get_btn):
            btn.setFixedHeight(28)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.setFocusPolicy(Qt.NoFocus)

        self.tab_stats_btn.clicked.connect(lambda: self.switch_right_tab(0))
        self.tab_evos_btn.clicked.connect(lambda: self.switch_right_tab(1))
        self.tab_how_to_get_btn.clicked.connect(lambda: self.switch_right_tab(2))

        tab_h.addWidget(self.tab_stats_btn)
        tab_h.addWidget(self.tab_evos_btn)
        tab_h.addWidget(self.tab_how_to_get_btn)
        self._update_tab_button_styles()

        right_box.addWidget(self.tab_bar_frame)

        # -------------------------------------------------------------
        # STACKED WIDGET (STATS / EVOS & PATHS / HOW TO GET)
        # -------------------------------------------------------------
        self.right_stack = QStackedWidget()
        self.right_stack.setFixedWidth(310)

        # Tab 0: Base Stats Card
        self.create_stats_card()
        self.right_stack.addWidget(self.card_stats)

        # Tab 1: Evolution Chains Card
        self.create_evos_card()
        self.right_stack.addWidget(self.card_evos)

        # Tab 2: How to Get Card
        self.create_how_to_get_card()
        self.right_stack.addWidget(self.card_how_to_get)

        right_box.addWidget(self.right_stack, 1)
        body_layout.addLayout(right_box)

        root_layout.addLayout(body_layout, 1)

    def switch_right_tab(self, idx: int):
        """Switch between STATS (0), EVOS & PATHS (1), and HOW TO GET (2)."""
        if self.current_right_tab != idx:
            play_sfx("menu_move.wav")
        self.current_right_tab = idx
        self.right_stack.setCurrentIndex(idx)
        self._update_tab_button_styles()

    def _update_tab_button_styles(self):
        """Authentic Emerald/GBA retro tab styling."""
        active_style = """
            QPushButton {
                background-color: #ef3131;
                color: #ffffff;
                border: 2px solid #b91c1c;
                border-radius: 6px;
                font-family: 'JetBrainsMono Nerd Font', monospace;
                font-size: 10px;
                font-weight: 900;
                padding: 2px 4px;
            }
        """
        inactive_style = """
            QPushButton {
                background-color: #ffffff;
                color: #475569;
                border: 2px solid #cbd5e1;
                border-radius: 6px;
                font-family: 'JetBrainsMono Nerd Font', monospace;
                font-size: 10px;
                font-weight: bold;
                padding: 2px 4px;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                color: #0f172a;
                border-color: #94a3b8;
            }
        """
        self.tab_stats_btn.setStyleSheet(active_style if self.current_right_tab == 0 else inactive_style)
        self.tab_evos_btn.setStyleSheet(active_style if self.current_right_tab == 1 else inactive_style)
        self.tab_how_to_get_btn.setStyleSheet(active_style if self.current_right_tab == 2 else inactive_style)

    def show_stats_tab(self):
        self.switch_right_tab(0)

    def show_evos_tab(self):
        self.switch_right_tab(1)

    def show_how_to_get_tab(self):
        self.switch_right_tab(2)

    def create_stats_card(self):
        """Tab 0: Authentic Base Stats Card."""
        self.card_stats = QFrame()
        self.card_stats.setFixedWidth(310)
        self.card_stats.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 2px solid #293131;
                border-radius: 8px;
            }
        """)
        cs_layout = QVBoxLayout(self.card_stats)
        cs_layout.setContentsMargins(14, 12, 14, 12)
        cs_layout.setSpacing(8)

        stats_hdr = QHBoxLayout()
        lbl_s_title = QLabel("BASE STATS")
        lbl_s_title.setStyleSheet("color: #0f172a; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 13px; font-weight: 900; letter-spacing: 1px;")
        self.lbl_bst = QLabel("BST: 0")
        self.lbl_bst.setStyleSheet("color: #ef4444; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 12px; font-weight: 900;")
        stats_hdr.addWidget(lbl_s_title)
        stats_hdr.addStretch()
        stats_hdr.addWidget(self.lbl_bst)
        cs_layout.addLayout(stats_hdr)

        # 6 Stat Rows: HP, AT, DE, SA, SD, SP
        self.stat_widgets = {}
        for code, label in [("hp", "HP"), ("atk", "AT"), ("def", "DE"), ("spa", "SA"), ("spd", "SD"), ("spe", "SP")]:
            row = QHBoxLayout()
            row.setSpacing(8)

            lbl = QLabel(label)
            lbl.setFixedWidth(28)
            lbl.setStyleSheet("color: #0f172a; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 12px; font-weight: 900;")
            row.addWidget(lbl)

            bar = StatBarWidget()
            row.addWidget(bar, 1)

            val_lbl = QLabel("0")
            val_lbl.setFixedWidth(34)
            val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val_lbl.setStyleSheet("color: #334155; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 12px; font-weight: bold;")
            row.addWidget(val_lbl)

            self.stat_widgets[code] = (bar, val_lbl)
            cs_layout.addLayout(row)

    def create_evos_card(self):
        """Tab 1: Evolution Chains & Branching Paths Card."""
        self.card_evos = QFrame()
        self.card_evos.setFixedWidth(310)
        self.card_evos.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 2px solid #293131;
                border-radius: 8px;
            }
        """)
        layout = QVBoxLayout(self.card_evos)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        hdr = QHBoxLayout()
        lbl_title = QLabel("🧬 EVOLUTIONS & PATHS")
        lbl_title.setStyleSheet("color: #0f172a; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 12px; font-weight: 900; letter-spacing: 1px;")
        hdr.addWidget(lbl_title)
        hdr.addStretch()
        layout.addLayout(hdr)

        self.evos_scroll = QScrollArea()
        self.evos_scroll.setWidgetResizable(True)
        self.evos_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                background: #f1f5f9; width: 6px; border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1; border-radius: 3px; min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { background: #94a3b8; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)

        self.evos_container = QWidget()
        self.evos_layout = QVBoxLayout(self.evos_container)
        self.evos_layout.setContentsMargins(0, 4, 0, 4)
        self.evos_layout.setSpacing(6)
        self.evos_scroll.setWidget(self.evos_container)

        layout.addWidget(self.evos_scroll, 1)

    def create_how_to_get_card(self):
        """Tab 2: How to Get Card (Habitats, Quests, Special Gifts)."""
        self.card_how_to_get = QFrame()
        self.card_how_to_get.setFixedWidth(310)
        self.card_how_to_get.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 2px solid #293131;
                border-radius: 8px;
            }
        """)
        layout = QVBoxLayout(self.card_how_to_get)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        hdr = QHBoxLayout()
        lbl_title = QLabel("📍 HOW TO GET")
        lbl_title.setStyleSheet("color: #0f172a; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 12px; font-weight: 900; letter-spacing: 1px;")
        hdr.addWidget(lbl_title)
        hdr.addStretch()

        self.how_status_badge = QLabel("○ MISSING")
        self.how_status_badge.setStyleSheet("""
            background-color: #f1f5f9; color: #64748b; border: 1px solid #cbd5e1;
            border-radius: 4px; font-family: 'JetBrainsMono Nerd Font', monospace;
            font-size: 10px; font-weight: 900; padding: 2px 6px;
        """)
        hdr.addWidget(self.how_status_badge)
        layout.addLayout(hdr)

        self.how_scroll = QScrollArea()
        self.how_scroll.setWidgetResizable(True)
        self.how_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                background: #f1f5f9; width: 6px; border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1; border-radius: 3px; min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { background: #94a3b8; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)

        self.how_container = QWidget()
        self.how_layout = QVBoxLayout(self.how_container)
        self.how_layout.setContentsMargins(0, 4, 0, 4)
        self.how_layout.setSpacing(6)
        self.how_scroll.setWidget(self.how_container)

        layout.addWidget(self.how_scroll, 1)

    # -------------------------------------------------------------
    # DATA LOADING & SAVE SYNCHRONIZATION
    # -------------------------------------------------------------
    def load_data(self):
        """Load Pokémon database and user save status."""
        self.pokemon_by_nat.clear()
        self.nat_nums.clear()
        self.sp_to_nat.clear()
        self.nat_to_base_id.clear()
        self.all_pokemon_records.clear()
        self.nat_to_all_sps.clear()
        self.evo_forward.clear()
        self.evo_backward.clear()
        self.legendaries_list.clear()
        self.encounters_by_sp_id.clear()

        # 1. Parse Save File if present
        if os.path.exists(self.save_path):
            try:
                parser = quetzal_save_reader.QuetzalSaveParser(self.save_path)
                self.seen_species = parser.get_all_seen_species()
                self.caught_species = parser.get_all_caught_species()
            except Exception as e:
                print(f"[PokedexRetroView] Save file parse error: {e}")
                self.seen_species = set()
                self.caught_species = set()
        else:
            self.seen_species = set()
            self.caught_species = set()

        # 2. Query SQLite Database for 1025 National Dex Entries, Evolutions, Encounters, Legendaries
        if os.path.exists(self.db_path):
            try:
                con = sqlite3.connect(self.db_path)
                cur = con.cursor()

                # Build full pokemon records & species -> nat mapping
                all_p = cur.execute("""
                    SELECT id, name, hp, atk, def, spa, spd, spe, bst, type1, type2, catch_rate, hidden_ability, abilities, national_dex_num
                    FROM pokemon
                """).fetchall()

                for pid, name, hp, atk, df, spa, spd, spe, bst, t1, t2, cr, hab, ab, nat in all_p:
                    nat_num = nat if nat is not None else pid
                    self.sp_to_nat[pid] = nat_num
                    self.all_pokemon_records[pid] = {
                        "species_id": pid, "name": name, "national_dex_num": nat_num,
                        "hp": hp, "atk": atk, "def": df, "spa": spa, "spd": spd, "spe": spe,
                        "bst": bst or (hp + atk + df + spa + spd + spe),
                        "type1": t1, "type2": t2, "catch_rate": cr,
                        "hidden_ability": hab, "abilities": ab
                    }
                    self.nat_to_all_sps[nat_num].append(pid)

                # Select base form for each national dex number 1..1025
                rows = cur.execute("""
                    SELECT p.national_dex_num, p.id, p.name, p.hp, p.atk, p.def, p.spa, p.spd, p.spe, p.bst, p.type1, p.type2, p.abilities, p.hidden_ability, p.catch_rate
                    FROM pokemon p
                    WHERE p.id IN (
                        SELECT min(id) FROM pokemon WHERE national_dex_num IS NOT NULL GROUP BY national_dex_num
                    )
                    ORDER BY p.national_dex_num ASC
                """).fetchall()

                for r in rows:
                    nat, pid, name, hp, atk, df, spa, spd, spe, bst, t1, t2, ab, hab, cr = r
                    self.pokemon_by_nat[nat] = {
                        "national_dex_num": nat,
                        "species_id": pid,
                        "name": name,
                        "hp": hp,
                        "atk": atk,
                        "def": df,
                        "spa": spa,
                        "spd": spd,
                        "spe": spe,
                        "bst": bst or (hp + atk + df + spa + spd + spe),
                        "type1": t1,
                        "type2": t2,
                        "abilities": ab,
                        "hidden_ability": hab,
                        "catch_rate": cr
                    }
                    self.nat_nums.append(nat)
                    self.nat_to_base_id[nat] = pid

                # 3. Evolutions Graph
                for src_id, sname, tgt_id, tname, method in cur.execute("SELECT pokemon_id, pokemon_name, target_id, target_name, method_desc FROM evolutions").fetchall():
                    self.evo_forward[src_id].append((tgt_id, method))
                    self.evo_backward[tgt_id].append((src_id, method))

                # 4. Legendaries Master Guide
                for name, gen, lvl, loc, req, syn, notes in cur.execute("SELECT name, generation, level, location, requirements, synergy, notes FROM legendaries").fetchall():
                    self.legendaries_list.append({
                        "name": name, "generation": gen, "level": lvl, "location": loc,
                        "requirements": req, "synergy": syn, "notes": notes
                    })

                # 5. Wild Route Encounters
                for rgn, mg, mn, loc_name, meth, slot, chance, min_lv, max_lv, sp_id, sp_name in cur.execute("SELECT region, map_group, map_num, location_name, method, slot, chance, min_level, max_level, species_id, species_name FROM encounters").fetchall():
                    self.encounters_by_sp_id[sp_id].append({
                        "region": rgn, "location_name": loc_name, "method": meth,
                        "chance": chance, "min_level": min_lv, "max_level": max_lv,
                        "species_id": sp_id, "species_name": sp_name
                    })

                con.close()
            except Exception as e:
                print(f"[PokedexRetroView] DB query error: {e}")

        self.update_national_summary()
        self.populate_list()

    def update_national_summary(self):
        """Update the National Seen & Own counts."""
        # Calculate distinct national dex entries seen/caught
        seen_nats = set(self.sp_to_nat.get(s, s) for s in self.seen_species if self.sp_to_nat.get(s, s) in self.pokemon_by_nat)
        caught_nats = set(self.sp_to_nat.get(s, s) for s in self.caught_species if self.sp_to_nat.get(s, s) in self.pokemon_by_nat)

        seen_cnt = len(seen_nats)
        caught_cnt = len(caught_nats)
        total_nat = len(self.pokemon_by_nat) or 1025

        self.lbl_seen_val.setText(str(seen_cnt))
        self.lbl_own_val.setText(str(caught_cnt))
        pct = (caught_cnt / total_nat) * 100.0 if total_nat > 0 else 0.0
        self.lbl_completion.setText(f"{caught_cnt} / {total_nat} ({pct:.1f}% Caught)")

    def is_seen(self, nat: int) -> bool:
        """Check if national dex number has been seen."""
        base_id = self.nat_to_base_id.get(nat, nat)
        return (base_id in self.seen_species) or (nat in self.seen_species) or (self.is_caught(nat))

    def is_caught(self, nat: int) -> bool:
        """Check if national dex number has been caught."""
        base_id = self.nat_to_base_id.get(nat, nat)
        return (base_id in self.caught_species) or (nat in self.caught_species)

    # -------------------------------------------------------------
    # LIST POPULATION & FILTERING
    # -------------------------------------------------------------
    def populate_list(self):
        """Populate the left scrollable list with 4-digit numbers and species names."""
        self.pokemon_list.blockSignals(True)
        self.pokemon_list.clear()

        query = self.search_query.strip().lower()
        selected_row = -1

        for nat in self.nat_nums:
            mon = self.pokemon_by_nat[nat]
            seen = self.is_seen(nat)
            caught = self.is_caught(nat)

            # Filter Mode Check
            if self.filter_mode == "SEEN" and not seen:
                continue
            if self.filter_mode == "CAUGHT" and not caught:
                continue

            # Query Filter Check
            nat_str = f"{nat:04d}"
            name = mon["name"]
            display_name = name if seen else "-----------"

            if query:
                if query not in nat_str and query not in name.lower():
                    continue

            # Row text format: "0142  Aerodactyl"
            text = f"{nat_str}  {display_name}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, nat)

            if caught:
                item.setIcon(get_pokeball_icon())

            self.pokemon_list.addItem(item)
            if nat == self.current_nat:
                selected_row = self.pokemon_list.count() - 1

        self.pokemon_list.blockSignals(False)

        if selected_row >= 0:
            self.pokemon_list.setCurrentRow(selected_row)
        elif self.pokemon_list.count() > 0:
            self.pokemon_list.setCurrentRow(0)

    def on_search_changed(self, text: str):
        """Filter list as the user types."""
        self.search_query = text
        self.populate_list()

    def set_filter_mode(self, mode: str):
        """Change filter between ALL, SEEN, CAUGHT."""
        if self.filter_mode != mode:
            play_sfx("menu_move.wav")
            self.filter_mode = mode
            self._update_filter_button_styles()
            self.populate_list()

    def _update_filter_button_styles(self):
        """Update active chip styling for filter buttons."""
        buttons = [
            (self.btn_filter_all, "ALL"),
            (self.btn_filter_seen, "SEEN"),
            (self.btn_filter_own, "CAUGHT")
        ]
        for btn, mode in buttons:
            if self.filter_mode == mode:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #ef3131;
                        color: #ffffff;
                        border: 2px solid #b91c1c;
                        border-radius: 6px;
                        font-family: 'JetBrainsMono Nerd Font', monospace;
                        font-size: 11px;
                        font-weight: 900;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #ffffff;
                        color: #475569;
                        border: 2px solid #cbd5e1;
                        border-radius: 6px;
                        font-family: 'JetBrainsMono Nerd Font', monospace;
                        font-size: 11px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #f1f5f9;
                        color: #0f172a;
                    }
                """)

    def on_list_item_changed(self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]):
        """Handle selection change in the list."""
        if current is None:
            return
        nat = current.data(Qt.UserRole)
        if nat and nat != self.current_nat:
            play_sfx("menu_move.wav")
            self.select_pokemon(nat)

    def step_selection(self, delta: int):
        """Step selection by delta (-1 or +1) in carousel or list."""
        row = self.pokemon_list.currentRow()
        new_row = row + delta
        if 0 <= new_row < self.pokemon_list.count():
            play_sfx("menu_move.wav")
            self.pokemon_list.setCurrentRow(new_row)

    # -------------------------------------------------------------
    # SELECTION & POKÉMON DETAILS DISPLAY
    # -------------------------------------------------------------
    def select_pokemon(self, nat: int):
        """Display details for a specific national dex Pokémon."""
        if nat not in self.pokemon_by_nat:
            return
        self.current_nat = nat
        mon = self.pokemon_by_nat[nat]
        seen = self.is_seen(nat)
        caught = self.is_caught(nat)

        # 1. Update Center Sprite & Name
        nat_str = f"{nat:04d}"
        if seen:
            self.main_name_lbl.setText(f"{nat_str} {mon['name'].upper()}")
            self.load_main_sprite(mon["species_id"], is_silhouette=False)
            self.update_type_badges(mon.get("type1"), mon.get("type2"))
            hab = f" • Hidden: {mon['hidden_ability']}" if mon.get("hidden_ability") else ""
            self.extra_info_lbl.setText(f"Abilities: {mon.get('abilities', 'None')}{hab} • Catch Rate: {mon.get('catch_rate', 45)}")
        else:
            self.main_name_lbl.setText(f"{nat_str} -----------")
            self.load_main_sprite(mon["species_id"], is_silhouette=True)
            self.update_type_badges("???", None)
            self.extra_info_lbl.setText("Habitat: Unexplored • Status: UNSEEN")

        # 2. Update Previous & Next Previews for Carousel
        curr_idx = self.nat_nums.index(nat) if nat in self.nat_nums else 0
        prev_nat = self.nat_nums[curr_idx - 1] if curr_idx > 0 else None
        next_nat = self.nat_nums[curr_idx + 1] if curr_idx < len(self.nat_nums) - 1 else None

        if prev_nat:
            p_mon = self.pokemon_by_nat[prev_nat]
            p_seen = self.is_seen(prev_nat)
            p_name = p_mon["name"] if p_seen else "-----------"
            self.prev_label.setText(f"▲ {prev_nat:04d} {p_name}")
            self.load_preview_sprite(self.prev_sprite, p_mon["species_id"], not p_seen)
            self.prev_container.setVisible(True)
        else:
            self.prev_container.setVisible(False)

        if next_nat:
            n_mon = self.pokemon_by_nat[next_nat]
            n_seen = self.is_seen(next_nat)
            n_name = n_mon["name"] if n_seen else "-----------"
            self.next_label.setText(f"▼ {next_nat:04d} {n_name}")
            self.load_preview_sprite(self.next_sprite, n_mon["species_id"], not n_seen)
            self.next_container.setVisible(True)
        else:
            self.next_container.setVisible(False)

        # 3. Update Base Stats
        if seen:
            self.lbl_bst.setText(f"BST: {mon['bst']}")
            for code in ["hp", "atk", "def", "spa", "spd", "spe"]:
                val = mon.get(code, 0)
                bar, val_lbl = self.stat_widgets[code]
                bar.set_value(val)
                val_lbl.setText(str(val))
        else:
            self.lbl_bst.setText("BST: ???")
            for code in ["hp", "atk", "def", "spa", "spd", "spe"]:
                bar, val_lbl = self.stat_widgets[code]
                bar.set_value(0)
                val_lbl.setText("???")

        # 4. Update Evolution Chains Card
        self.update_evos_card(nat)

        # 5. Update How To Get Card
        self.update_how_to_get_card(nat)

        self.pokemon_selected.emit(nat)

    def load_main_sprite(self, species_id: int, is_silhouette: bool):
        """Load crisp large center sprite with pixelated transformation."""
        pm = self.get_sprite_pixmap(species_id, is_silhouette)
        if pm and not pm.isNull():
            # Scale large with FastTransformation (nearest neighbor) to keep pixel art sharp
            scaled = pm.scaled(180, 180, Qt.KeepAspectRatio, Qt.FastTransformation)
            self.main_sprite.setPixmap(scaled)
        else:
            self.main_sprite.setText("❓")

    def load_preview_sprite(self, target_lbl: QLabel, species_id: int, is_silhouette: bool):
        """Load smaller preview sprite for carousel top/bottom."""
        pm = self.get_sprite_pixmap(species_id, is_silhouette)
        if pm and not pm.isNull():
            scaled = pm.scaled(52, 52, Qt.KeepAspectRatio, Qt.FastTransformation)
            target_lbl.setPixmap(scaled)
        else:
            target_lbl.setText("❓")

    def get_sprite_pixmap(self, species_id: int, is_silhouette: bool) -> Optional[QPixmap]:
        """Fetch sprite or silhouette from disk cache or asset directory."""
        if is_silhouette:
            if species_id in self.silhouette_cache:
                return self.silhouette_cache[species_id]
            sil_path = os.path.join(SILHOUETTES_DIR, f"{species_id}.png")
            if os.path.exists(sil_path):
                pm = QPixmap(sil_path)
                self.silhouette_cache[species_id] = pm
                return pm

        if species_id in self.sprite_cache:
            return self.sprite_cache[species_id]

        sp_path = os.path.join(SPRITES_DIR, f"{species_id}.png")
        if os.path.exists(sp_path):
            pm = QPixmap(sp_path)
            self.sprite_cache[species_id] = pm
            if is_silhouette:
                # Generate silhouette on the fly
                img = pm.toImage()
                for y in range(img.height()):
                    for x in range(img.width()):
                        c = img.pixelColor(x, y)
                        if c.alpha() > 20:
                            img.setPixelColor(x, y, QColor(30, 41, 59, 240))
                sil_pm = QPixmap.fromImage(img)
                self.silhouette_cache[species_id] = sil_pm
                return sil_pm
            return pm
        return None

    def update_type_badges(self, t1: Optional[str], t2: Optional[str]):
        """Render retro colored type pills."""
        # Clear existing
        while self.types_layout.count() > 0:
            item = self.types_layout.takeAt(0)
            if item.widget():
                w = item.widget()
                w.hide()
                w.setParent(None)
                w.deleteLater()

        if not t1 or t1 == "???":
            lbl = QLabel("UNKNOWN")
            lbl.setStyleSheet("""
                background-color: #64748b;
                color: #ffffff;
                font-family: 'JetBrainsMono Nerd Font', monospace;
                font-size: 11px;
                font-weight: 900;
                padding: 3px 12px;
                border-radius: 4px;
            """)
            self.types_layout.addWidget(lbl)
            return

        type_colors = {
            "Normal": "#94a3b8", "Fire": "#ef4444", "Water": "#3b82f6",
            "Grass": "#22c55e", "Electric": "#eab308", "Ice": "#06b6d4",
            "Fighting": "#b91c1c", "Poison": "#a855f7", "Ground": "#d97706",
            "Flying": "#818cf8", "Psychic": "#ec4899", "Bug": "#84cc16",
            "Rock": "#78716c", "Ghost": "#6366f1", "Dragon": "#4f46e5",
            "Steel": "#64748b", "Dark": "#334155", "Fairy": "#f472b6"
        }

        for t in (t1, t2):
            if not t or t == "None":
                continue
            color = type_colors.get(t, "#64748b")
            lbl = QLabel(t.upper())
            lbl.setStyleSheet(f"""
                background-color: {color};
                color: #ffffff;
                font-family: 'JetBrainsMono Nerd Font', monospace;
                font-size: 11px;
                font-weight: 900;
                padding: 3px 14px;
                border-radius: 4px;
            """)
            self.types_layout.addWidget(lbl)

    # -------------------------------------------------------------
    # EVOLUTION CHAINS & HOW TO GET CARDS
    # -------------------------------------------------------------
    def on_evo_card_clicked(self, nat: int):
        """1-click interactive jump when clicking an evolution card."""
        if nat and nat in self.pokemon_by_nat:
            play_sfx("menu_select.wav")
            if self.filter_mode != "ALL" and not (self.filter_mode == "SEEN" and self.is_seen(nat)) and not (self.filter_mode == "CAUGHT" and self.is_caught(nat)):
                self.set_filter_mode("ALL")
            self.select_pokemon(nat)
            for row in range(self.pokemon_list.count()):
                item = self.pokemon_list.item(row)
                if item and item.data(Qt.UserRole) == nat:
                    self.pokemon_list.blockSignals(True)
                    self.pokemon_list.setCurrentRow(row)
                    self.pokemon_list.blockSignals(False)
                    break

    def on_pre_evo_btn_clicked(self, nat: int):
        """1-click jump to pre-evolution from How to Get card."""
        self.on_evo_card_clicked(nat)

    def update_evos_card(self, nat: int):
        """Render full evolution tree with branching paths and interactive jump."""
        while self.evos_layout.count() > 0:
            item = self.evos_layout.takeAt(0)
            if item.widget():
                w = item.widget()
                w.setParent(None)
                w.deleteLater()
            elif item.layout():
                while item.layout().count() > 0:
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        w = sub.widget()
                        w.setParent(None)
                        w.deleteLater()

        # Target species candidates
        candidate_sps = [
            s for s in self.nat_to_all_sps.get(nat, [self.nat_to_base_id.get(nat, nat)])
            if s in self.evo_forward or s in self.evo_backward
        ]

        if not candidate_sps:
            # Does not evolve badge
            no_evo_frame = QFrame()
            no_evo_frame.setStyleSheet("""
                QFrame {
                    background-color: #f8fafc;
                    border: 2px dashed #94a3b8;
                    border-radius: 8px;
                }
            """)
            ne_layout = QVBoxLayout(no_evo_frame)
            ne_layout.setContentsMargins(14, 20, 14, 20)
            ne_layout.setSpacing(8)

            badge = QLabel("🔒 DOES NOT EVOLVE")
            badge.setAlignment(Qt.AlignCenter)
            badge.setStyleSheet("""
                color: #475569;
                background-color: #e2e8f0;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                font-family: 'JetBrainsMono Nerd Font', monospace;
                font-size: 11px;
                font-weight: 900;
                padding: 4px 10px;
            """)
            ne_layout.addWidget(badge)

            lbl_desc = QLabel("This Pokémon does not evolve into or from any other species.")
            lbl_desc.setWordWrap(True)
            lbl_desc.setAlignment(Qt.AlignCenter)
            lbl_desc.setStyleSheet("color: #64748b; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 10px; font-weight: bold;")
            ne_layout.addWidget(lbl_desc)

            self.evos_layout.addWidget(no_evo_frame)
            self.evos_layout.addStretch()
            return

        # Find connected components and roots
        visited_all = set()
        connected_components = []

        for start_sp in candidate_sps:
            if start_sp in visited_all:
                continue
            component = set()
            q = deque([start_sp])
            while q:
                curr = q.popleft()
                if curr in component:
                    continue
                component.add(curr)
                for nxt, _ in self.evo_forward.get(curr, []):
                    if nxt not in component:
                        q.append(nxt)
                for prv, _ in self.evo_backward.get(curr, []):
                    if prv not in component:
                        q.append(prv)
            visited_all.update(component)

            # Find roots (nodes with no in-edges within this component)
            roots = [sp for sp in component if not any(src in component for src, _ in self.evo_backward.get(sp, []))]
            connected_components.append((roots, component))

        rendered_sps = set()

        def render_subtree(node_sp: int, target_layout: QVBoxLayout, is_root: bool = False):
            if node_sp in rendered_sps:
                return
            rendered_sps.add(node_sp)

            rec = self.all_pokemon_records.get(node_sp, {})
            node_nat = rec.get("national_dex_num", self.sp_to_nat.get(node_sp, node_sp))
            name = rec.get("name", "Unknown")
            t1 = rec.get("type1")
            t2 = rec.get("type2")
            form_name = get_species_form_name(node_sp, self.nat_to_base_id.get(node_nat, node_nat))
            is_seen = self.is_seen(node_nat)
            is_curr = (node_nat == self.current_nat)
            pixmap = self.get_sprite_pixmap(node_sp, not is_seen)

            card = EvoNodeCard(node_sp, node_nat, name, t1, t2, is_curr, is_seen, pixmap, form_name, on_click=self.on_evo_card_clicked)
            target_layout.addWidget(card)

            # Forward edges
            raw_children = self.evo_forward.get(node_sp, [])
            if not raw_children:
                return

            tgt_methods = defaultdict(list)
            for tgt_id, meth in raw_children:
                fmt_meth = format_evolution_method(meth)
                if fmt_meth not in tgt_methods[tgt_id]:
                    tgt_methods[tgt_id].append(fmt_meth)

            if len(tgt_methods) > 1:
                # Branching node
                bf = QFrame()
                bf.setStyleSheet("""
                    QFrame {
                        background-color: #f8fafc;
                        border-left: 3px solid #10b981;
                        border-radius: 4px;
                    }
                """)
                b_vbox = QVBoxLayout(bf)
                b_vbox.setContentsMargins(6, 6, 2, 6)
                b_vbox.setSpacing(4)

                b_lbl = QLabel(f"↳ {len(tgt_methods)} Evolution Branches:")
                b_lbl.setStyleSheet("color: #047857; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 10px; font-weight: 900;")
                b_vbox.addWidget(b_lbl)

                for tgt_id, methods in tgt_methods.items():
                    m_text = " / ".join(methods)
                    arrow = create_evo_arrow(m_text, is_branch=True)
                    b_vbox.addWidget(arrow)
                    render_subtree(tgt_id, b_vbox, is_root=False)

                target_layout.addWidget(bf)
            else:
                # Linear evolution
                tgt_id, methods = list(tgt_methods.items())[0]
                m_text = " / ".join(methods)
                arrow = create_evo_arrow(m_text, is_branch=False)
                target_layout.addWidget(arrow)
                render_subtree(tgt_id, target_layout, is_root=False)

        for comp_idx, (roots, comp) in enumerate(connected_components):
            if len(connected_components) > 1:
                # E.g. Standard line vs Galarian line
                comp_root = roots[0] if roots else 0
                r_name = self.all_pokemon_records.get(comp_root, {}).get("name", "Form")
                r_form = get_species_form_name(comp_root, self.nat_to_base_id.get(self.sp_to_nat.get(comp_root, comp_root), comp_root))
                tag = f"{r_form} Line" if r_form != "Standard" else "Standard Line"
                line_badge = QLabel(f"🌐 {tag}:")
                line_badge.setStyleSheet("color: #0284c7; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 10px; font-weight: 900; margin-top: 4px;")
                self.evos_layout.addWidget(line_badge)

            for root in roots:
                render_subtree(root, self.evos_layout, is_root=True)

        self.evos_layout.addStretch()

    def update_how_to_get_card(self, nat: int):
        """Render wild encounters grouped by region, legendary quests, or evolution acquisition."""
        while self.how_layout.count() > 0:
            item = self.how_layout.takeAt(0)
            if item.widget():
                w = item.widget()
                w.setParent(None)
                w.deleteLater()
            elif item.layout():
                while item.layout().count() > 0:
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        w = sub.widget()
                        w.setParent(None)
                        w.deleteLater()

        # Status badge update
        is_c = self.is_caught(nat)
        if is_c:
            self.how_status_badge.setText("✓ CAUGHT")
            self.how_status_badge.setStyleSheet("""
                background-color: #ecfdf5; color: #047857; border: 1px solid #10b981;
                border-radius: 4px; font-family: 'JetBrainsMono Nerd Font', monospace;
                font-size: 10px; font-weight: 900; padding: 2px 6px;
            """)
        else:
            self.how_status_badge.setText("○ MISSING")
            self.how_status_badge.setStyleSheet("""
                background-color: #f1f5f9; color: #64748b; border: 1px solid #cbd5e1;
                border-radius: 4px; font-family: 'JetBrainsMono Nerd Font', monospace;
                font-size: 10px; font-weight: 900; padding: 2px 6px;
            """)

        mon = self.pokemon_by_nat.get(nat, {})
        mon_name = mon.get("name", "")
        target_sps = self.nat_to_all_sps.get(nat, [self.nat_to_base_id.get(nat, nat)])

        # 1. Legendary Check
        matched_legs = [
            leg for leg in self.legendaries_list
            if leg["name"].lower() == mon_name.lower() or mon_name.lower() in leg["name"].lower()
        ]

        if matched_legs:
            for leg in matched_legs:
                leg_card = QFrame()
                leg_card.setStyleSheet("""
                    QFrame {
                        background-color: #fffbeb;
                        border: 2px solid #f59e0b;
                        border-radius: 6px;
                    }
                """)
                lc = QVBoxLayout(leg_card)
                lc.setContentsMargins(8, 8, 8, 8)
                lc.setSpacing(4)

                lt = QLabel(f"👑 LEGENDARY: {leg['name'].upper()}")
                lt.setStyleSheet("color: #b45309; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 11px; font-weight: 900;")
                lc.addWidget(lt)

                loc_lbl = QLabel(f"📍 Location: {leg['location']}")
                loc_lbl.setWordWrap(True)
                loc_lbl.setStyleSheet("color: #0f172a; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 10px; font-weight: bold;")
                lc.addWidget(loc_lbl)

                lvl_lbl = QLabel(f"⚔️ Encounter: {leg['level']} • {leg.get('generation', 'Hoenn Native')}")
                lvl_lbl.setStyleSheet("color: #475569; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 10px; font-weight: bold;")
                lc.addWidget(lvl_lbl)

                req_t = QLabel("📜 Storyline & Puzzle Requirements:")
                req_t.setStyleSheet("color: #b45309; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 9px; font-weight: 900; margin-top: 2px;")
                lc.addWidget(req_t)

                req_lbl = QLabel(leg["requirements"])
                req_lbl.setWordWrap(True)
                req_lbl.setStyleSheet("color: #334155; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 9px;")
                lc.addWidget(req_lbl)

                if leg.get("synergy"):
                    syn_lbl = QLabel(f"⚡ Recommended Synergy: {leg['synergy']}")
                    syn_lbl.setWordWrap(True)
                    syn_lbl.setStyleSheet("color: #0369a1; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 9px; font-weight: bold;")
                    lc.addWidget(syn_lbl)

                if leg.get("notes"):
                    notes_lbl = QLabel(f"💡 Notes: {leg['notes']}")
                    notes_lbl.setWordWrap(True)
                    notes_lbl.setStyleSheet("color: #64748b; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 9px; font-style: italic;")
                    lc.addWidget(notes_lbl)

                self.how_layout.addWidget(leg_card)

        # 2. Special Gifts & Events Check
        if nat in SPECIAL_GIFTS_DATABASE:
            gift_card = QFrame()
            gift_card.setStyleSheet("""
                QFrame {
                    background-color: #eff6ff;
                    border: 2px solid #3b82f6;
                    border-radius: 6px;
                }
            """)
            gc = QVBoxLayout(gift_card)
            gc.setContentsMargins(8, 8, 8, 8)
            gc.setSpacing(4)

            gt = QLabel("🎁 SPECIAL ACQUISITION / GIFT")
            gt.setStyleSheet("color: #1d4ed8; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 11px; font-weight: 900;")
            gc.addWidget(gt)

            g_desc = QLabel(SPECIAL_GIFTS_DATABASE[nat])
            g_desc.setWordWrap(True)
            g_desc.setStyleSheet("color: #1e293b; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 10px; font-weight: bold;")
            gc.addWidget(g_desc)

            self.how_layout.addWidget(gift_card)

        # 3. Wild Route Encounters
        all_encs = []
        for sp_id in target_sps:
            all_encs.extend(self.encounters_by_sp_id.get(sp_id, []))

        by_region = defaultdict(lambda: defaultdict(lambda: {"min_lv": 999, "max_lv": 0, "chance": 0}))
        for enc in all_encs:
            rgn = enc["region"]
            loc = enc["location_name"]
            meth = enc["method"]
            entry = by_region[rgn][(loc, meth)]
            entry["min_lv"] = min(entry["min_lv"], enc["min_level"])
            entry["max_lv"] = max(entry["max_lv"], enc["max_level"])
            entry["chance"] += enc["chance"]

        total_loc_count = sum(len(locs) for locs in by_region.values())

        if total_loc_count > 0:
            wild_hdr = QLabel(f"🌿 WILD HABITATS ({total_loc_count} spots)")
            wild_hdr.setStyleSheet("color: #0f172a; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 11px; font-weight: 900; margin-top: 4px;")
            self.how_layout.addWidget(wild_hdr)

            region_order = ["Hoenn", "Kanto", "Johto", "Sevii Islands"]
            method_colors = {
                "Tall Grass": "#16a34a",
                "Surfing": "#0284c7",
                "Beach": "#d97706",
                "Hidden Rare": "#9333ea",
                "Rock Smash": "#78716c",
                "Fishing (Old Rod)": "#0d9488",
                "Fishing (Good Rod)": "#0891b2",
                "Fishing (Super Rod)": "#4f46e5"
            }

            for rgn in region_order:
                if rgn not in by_region or not by_region[rgn]:
                    continue
                r_box = QFrame()
                r_box.setStyleSheet("""
                    QFrame {
                        background-color: #ffffff;
                        border: 1px solid #cbd5e1;
                        border-radius: 6px;
                    }
                """)
                rb = QVBoxLayout(r_box)
                rb.setContentsMargins(6, 6, 6, 6)
                rb.setSpacing(4)

                r_title = QLabel(f"🌐 {rgn.upper()} REGION")
                r_title.setStyleSheet("color: #0284c7; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 10px; font-weight: 900;")
                rb.addWidget(r_title)

                for (loc, meth), data in sorted(by_region[rgn].items(), key=lambda x: (-x[1]["chance"], x[0][0])):
                    row_w = QWidget()
                    r_layout = QHBoxLayout(row_w)
                    r_layout.setContentsMargins(0, 0, 0, 0)
                    r_layout.setSpacing(4)

                    loc_lbl = QLabel(loc)
                    loc_lbl.setStyleSheet("color: #0f172a; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 10px; font-weight: bold;")
                    r_layout.addWidget(loc_lbl)

                    r_layout.addStretch()

                    m_color = method_colors.get(meth, "#64748b")
                    m_badge = QLabel(meth)
                    m_badge.setStyleSheet(f"""
                        background-color: {m_color};
                        color: #ffffff;
                        font-family: 'JetBrainsMono Nerd Font', monospace;
                        font-size: 8px;
                        font-weight: 900;
                        padding: 1px 4px;
                        border-radius: 3px;
                    """)
                    r_layout.addWidget(m_badge)

                    rate_lbl = QLabel(f"{data['chance']}%")
                    rate_lbl.setStyleSheet("color: #2563eb; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 9px; font-weight: 900;")
                    r_layout.addWidget(rate_lbl)

                    min_l, max_l = data["min_lv"], data["max_lv"]
                    lv_str = f"Lv.{min_l}" if min_l == max_l else f"Lv.{min_l}-{max_l}"
                    lv_lbl = QLabel(lv_str)
                    lv_lbl.setStyleSheet("color: #64748b; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 9px; font-weight: bold;")
                    r_layout.addWidget(lv_lbl)

                    rb.addWidget(row_w)

                self.how_layout.addWidget(r_box)

        # 4. Pre-evolution Check
        pre_evos = []
        for sp_id in target_sps:
            for src_id, meth in self.evo_backward.get(sp_id, []):
                pre_evos.append((src_id, meth))

        if total_loc_count == 0 and not matched_legs:
            # Evolution-Only or No Wild Spawns
            evo_only_card = QFrame()
            evo_only_card.setStyleSheet("""
                QFrame {
                    background-color: #fffbeb;
                    border: 2px solid #f59e0b;
                    border-radius: 6px;
                }
            """)
            eoc = QVBoxLayout(evo_only_card)
            eoc.setContentsMargins(8, 8, 8, 8)
            eoc.setSpacing(6)

            eoc_title = QLabel("🚫 NO WILD SPAWNS")
            eoc_title.setStyleSheet("color: #b45309; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 11px; font-weight: 900;")
            eoc.addWidget(eoc_title)

            if pre_evos:
                src_id, meth = pre_evos[0]
                src_rec = self.all_pokemon_records.get(src_id, {})
                src_nat = src_rec.get("national_dex_num", self.sp_to_nat.get(src_id, src_id))
                src_name = src_rec.get("name", "Pre-Evolution")
                m_desc = format_evolution_method(meth)

                desc = QLabel(f"No wild spawns. Obtain by evolving #{src_nat:04d} {src_name} at {m_desc}.")
                desc.setWordWrap(True)
                desc.setStyleSheet("color: #0f172a; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 10px; font-weight: bold;")
                eoc.addWidget(desc)

                jump_btn = QPushButton(f"▶ Jump to #{src_nat:04d} {src_name}")
                jump_btn.setFixedHeight(28)
                jump_btn.setCursor(QCursor(Qt.PointingHandCursor))
                jump_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #ef4444;
                        color: #ffffff;
                        border: 1px solid #b91c1c;
                        border-radius: 4px;
                        font-family: 'JetBrainsMono Nerd Font', monospace;
                        font-size: 10px;
                        font-weight: 900;
                    }
                    QPushButton:hover {
                        background-color: #dc2626;
                    }
                """)
                jump_btn.clicked.connect(lambda _, n=src_nat: self.on_pre_evo_btn_clicked(n))
                eoc.addWidget(jump_btn)
            else:
                if nat not in SPECIAL_GIFTS_DATABASE:
                    desc = QLabel("No wild spawns recorded in Hoenn, Kanto, Johto, or Sevii. Obtain via special in-game trade, event, or Battle Frontier reward.")
                    desc.setWordWrap(True)
                    desc.setStyleSheet("color: #64748b; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 10px;")
                    eoc.addWidget(desc)

            self.how_layout.addWidget(evo_only_card)

        elif total_loc_count > 0 and pre_evos:
            # Wild spawns exist AND pre-evolution exists
            src_id, meth = pre_evos[0]
            src_rec = self.all_pokemon_records.get(src_id, {})
            src_nat = src_rec.get("national_dex_num", self.sp_to_nat.get(src_id, src_id))
            src_name = src_rec.get("name", "Pre-Evolution")
            m_desc = format_evolution_method(meth)

            alt_box = QFrame()
            alt_box.setStyleSheet("""
                QFrame {
                    background-color: #f8fafc;
                    border: 1px dashed #cbd5e1;
                    border-radius: 6px;
                }
            """)
            ab = QVBoxLayout(alt_box)
            ab.setContentsMargins(6, 6, 6, 6)
            ab.setSpacing(4)

            alt_lbl = QLabel(f"💡 Also obtainable by evolving #{src_nat:04d} {src_name} ({m_desc}).")
            alt_lbl.setWordWrap(True)
            alt_lbl.setStyleSheet("color: #475569; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 9px; font-weight: bold;")
            ab.addWidget(alt_lbl)

            jump_btn = QPushButton(f"▶ Jump to #{src_nat:04d} {src_name}")
            jump_btn.setFixedHeight(24)
            jump_btn.setCursor(QCursor(Qt.PointingHandCursor))
            jump_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f1f5f9;
                    color: #0f172a;
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    font-family: 'JetBrainsMono Nerd Font', monospace;
                    font-size: 9px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #e2e8f0;
                }
            """)
            jump_btn.clicked.connect(lambda _, n=src_nat: self.on_pre_evo_btn_clicked(n))
            ab.addWidget(jump_btn)
            self.how_layout.addWidget(alt_box)

        self.how_layout.addStretch()

    # -------------------------------------------------------------
    # KEYBOARD NAVIGATION (GBA CONTROLS)
    # -------------------------------------------------------------
    def keyPressEvent(self, event):
        """Handle keyboard navigation for authentic GBA feel."""
        key = event.key()
        if key in (Qt.Key_Up, Qt.Key_K):
            self.step_selection(-1)
            event.accept()
        elif key in (Qt.Key_Down, Qt.Key_J):
            self.step_selection(1)
            event.accept()
        elif key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Tab):
            delta = 1 if key in (Qt.Key_Right, Qt.Key_Tab) else -1
            new_idx = (self.current_right_tab + delta) % 3
            self.switch_right_tab(new_idx)
            event.accept()
        elif key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Z):
            play_sfx("menu_select.wav")
            event.accept()
        elif key in (Qt.Key_Escape, Qt.Key_X):
            play_sfx("menu_cancel.wav")
            event.accept()
        elif key == Qt.Key_PageUp:
            self.step_selection(-10)
            event.accept()
        elif key == Qt.Key_PageDown:
            self.step_selection(10)
            event.accept()
        elif key == Qt.Key_Home:
            play_sfx("menu_move.wav")
            self.pokemon_list.setCurrentRow(0)
            event.accept()
        elif key == Qt.Key_End:
            play_sfx("menu_move.wav")
            self.pokemon_list.setCurrentRow(self.pokemon_list.count() - 1)
            event.accept()
        else:
            super().keyPressEvent(event)


class StatBarWidget(QWidget):
    """
    Renders authentic GBA horizontal stat bars matching Pokémon Emerald style.
    """
    def __init__(self, max_stat: int = 180, parent=None):
        super().__init__(parent)
        self.max_stat = max_stat
        self.value = 0
        self.setFixedHeight(14)
        self.setMinimumWidth(120)

    def set_value(self, val: int):
        self.value = max(0, val)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)  # Keep authentic crisp pixel edges

        w = self.width()
        h = self.height()
        bar_rect = QRectF(0, 1, w - 1, h - 2)

        # Recessed background track
        painter.setBrush(QColor("#f1f5f9"))
        painter.setPen(QPen(QColor("#293131"), 1.2))
        painter.drawRect(bar_rect)

        # Filled portion
        ratio = min(1.0, self.value / float(self.max_stat))
        fill_w = (bar_rect.width() - 2) * ratio

        if fill_w > 0:
            fill_rect = QRectF(bar_rect.x() + 1, bar_rect.y() + 1, fill_w, bar_rect.height() - 2)
            # Emerald Stat Bar Colors: Yellow-Green (#9cde6b / #ded66b / #d6de6b)
            if self.value >= 120:
                bar_color = QColor("#9cde6b")  # Vibrant Green
            elif self.value >= 80:
                bar_color = QColor("#d6de6b")  # Yellow-Green
            elif self.value >= 50:
                bar_color = QColor("#ded66b")  # Gold-Yellow
            else:
                bar_color = QColor("#f59e0b")  # Amber

            painter.setBrush(bar_color)
            painter.setPen(Qt.NoPen)
            painter.drawRect(fill_rect)


# ---------------------------------------------------------------------
# STANDALONE LAUNCHER / VERIFICATION TEST
# ---------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    window = PokedexRetroView()
    window.setWindowTitle("Authentic GBA Pokédex View")
    window.resize(1024, 680)
    window.show()
    sys.exit(app.exec())
