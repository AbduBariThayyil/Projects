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
from typing import Dict, List, Optional, Tuple, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem, QFrame,
    QScrollArea, QSizePolicy, QGraphicsOpacityEffect
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
        # PANE 3: RIGHT STACK (NATIONAL & BASE STATS)
        # -------------------------------------------------------------
        right_box = QVBoxLayout()
        right_box.setSpacing(14)

        # CARD 1: NATIONAL DEX PROGRESS
        self.card_national = QFrame()
        self.card_national.setFixedWidth(290)
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

        # CARD 2: BASE STATS CARD
        self.card_stats = QFrame()
        self.card_stats.setFixedWidth(290)
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

        right_box.addWidget(self.card_stats, 1)
        body_layout.addLayout(right_box)

        root_layout.addLayout(body_layout, 1)

    # -------------------------------------------------------------
    # DATA LOADING & SAVE SYNCHRONIZATION
    # -------------------------------------------------------------
    def load_data(self):
        """Load Pokémon database and user save status."""
        self.pokemon_by_nat.clear()
        self.nat_nums.clear()
        self.sp_to_nat.clear()
        self.nat_to_base_id.clear()

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

        # 2. Query SQLite Database for 1025 National Dex Entries
        if os.path.exists(self.db_path):
            try:
                con = sqlite3.connect(self.db_path)
                cur = con.cursor()

                # Build species -> nat mapping
                all_p = cur.execute("SELECT id, national_dex_num FROM pokemon").fetchall()
                for pid, nat in all_p:
                    self.sp_to_nat[pid] = nat if nat is not None else pid

                # Select base form for each national dex number 1..1025
                rows = cur.execute("""
                    SELECT p.national_dex_num, p.id, p.name, p.hp, p.atk, p.def, p.spa, p.spd, p.spe, p.bst, p.type1, p.type2, p.abilities, p.hidden_ability, p.catch_rate
                    FROM pokemon p
                    WHERE p.id IN (
                        SELECT min(id) FROM pokemon WHERE national_dex_num IS NOT NULL GROUP BY national_dex_num
                    )
                    ORDER BY p.national_dex_num ASC
                """).fetchall()
                con.close()

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
    # KEYBOARD NAVIGATION (GBA CONTROLS)
    # -------------------------------------------------------------
    def keyPressEvent(self, event):
        """Handle keyboard navigation for authentic GBA feel."""
        key = event.key()
        if key == Qt.Key_Up:
            self.step_selection(-1)
            event.accept()
        elif key == Qt.Key_Down:
            self.step_selection(1)
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
