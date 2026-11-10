#!/usr/bin/env python3
"""
Pokémon Quetzal Master Pokédex & Encounter Explorer (PySide6)
Offline comprehensive desktop app for Pokémon Quetzal:
- 1,499 Pokémon (All 9 Gens + Megas + Forms) with Base Stats, Types, Learnsets, Evolution Conditions
- 986 Moves with Power, Accuracy, Types, PP
- 4,487 Wild Encounter tables across all regions (Hoenn, Kanto, Sevii Islands)
- 104 Legendary & Mythical encounters with requirements and party synergies
- Interactive Poké Ball Catch Rate Calculator
"""

import sys
import os
import sqlite3
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QListWidget, QTableWidget, QTableWidgetItem, QTabWidget,
    QLabel, QHeaderView, QSplitter, QProgressBar, QComboBox, QGroupBox,
    QFormLayout, QSpinBox, QPushButton, QFrame, QTextEdit
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor, QPalette, QIcon

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quetzal_database.db")

TYPE_COLORS = {
    "Normal": "#A8A77A", "Fighting": "#C22E28", "Flying": "#A98FF3",
    "Poison": "#A33EA1", "Ground": "#E2BF65", "Rock": "#B6A136",
    "Bug": "#A6B91A", "Ghost": "#735797", "Steel": "#B7B7CE",
    "Fire": "#EE8130", "Water": "#6390F0", "Grass": "#7AC74C",
    "Electric": "#F7D02C", "Psychic": "#F95587", "Ice": "#96D9D6",
    "Dragon": "#6F35FC", "Dark": "#705746", "Fairy": "#D685AD",
    "Stellar": "#4682B4", "Mystery": "#68A090"
}

DARK_STYLESHEET = """
QMainWindow {
    background-color: #121214;
}
QWidget {
    color: #E1E1E6;
    font-family: 'Segoe UI', 'Ubuntu', sans-serif;
    font-size: 13px;
}
QTabWidget::pane {
    border: 1px solid #29292E;
    background-color: #19191B;
    border-radius: 6px;
}
QTabBar::tab {
    background-color: #202024;
    color: #A8A8B3;
    padding: 10px 20px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: bold;
}
QTabBar::tab:selected {
    background-color: #19191B;
    color: #00B37E;
    border-bottom: 2px solid #00B37E;
}
QLineEdit, QComboBox, QSpinBox {
    background-color: #202024;
    border: 1px solid #323238;
    border-radius: 6px;
    padding: 8px 12px;
    color: #FFFFFF;
    selection-background-color: #00B37E;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid #00B37E;
}
QListWidget {
    background-color: #202024;
    border: 1px solid #323238;
    border-radius: 6px;
    padding: 4px;
}
QListWidget::item {
    padding: 8px 10px;
    border-radius: 4px;
    margin-bottom: 2px;
}
QListWidget::item:selected {
    background-color: #00B37E;
    color: #FFFFFF;
    font-weight: bold;
}
QListWidget::item:hover:!selected {
    background-color: #29292E;
}
QTableWidget {
    background-color: #202024;
    border: 1px solid #323238;
    gridline-color: #29292E;
    border-radius: 6px;
}
QTableWidget::item {
    padding: 6px;
}
QHeaderView::section {
    background-color: #121214;
    color: #00B37E;
    font-weight: bold;
    padding: 8px;
    border: none;
    border-bottom: 1px solid #323238;
}
QProgressBar {
    background-color: #29292E;
    border-radius: 4px;
    text-align: center;
    color: #FFFFFF;
    font-size: 11px;
    font-weight: bold;
}
QProgressBar::chunk {
    border-radius: 4px;
    background-color: #00B37E;
}
QGroupBox {
    border: 1px solid #323238;
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 16px;
    font-weight: bold;
    color: #00B37E;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
}
"""

class QuetzalDexApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pokémon Quetzal Master Explorer (Gens 1-9 & All Regions)")
        self.resize(1280, 840)
        self.setStyleSheet(DARK_STYLESHEET)

        self.conn = sqlite3.connect(DB_PATH)
        self.cur = self.conn.cursor()

        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header Title
        title_box = QHBoxLayout()
        title_label = QLabel("⚡ Pokémon Quetzal Master Explorer")
        title_label.setFont(QFont("Arial", 18, QFont.Bold))
        title_label.setStyleSheet("color: #00B37E;")
        title_box.addWidget(title_label)

        sub_label = QLabel("1,499 Pokémon • 986 Moves • 4,487 Wild Locations (Hoenn, Kanto, Sevii) • 104 Legendaries")
        sub_label.setStyleSheet("color: #8D8D99; font-size: 12px;")
        title_box.addWidget(sub_label, alignment=Qt.AlignRight | Qt.AlignVCenter)
        main_layout.addLayout(title_box)

        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.create_pokedex_tab()
        self.create_encounters_tab()
        self.create_legendaries_tab()
        self.create_calculator_tab()

    # ==========================================
    # TAB 1: POKÉDEX & LEARNSET EXPLORER
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
        self.header_card.setStyleSheet("background-color: #202024; border-radius: 8px; padding: 14px;")
        card_layout = QHBoxLayout(self.header_card)

        self.mon_name_lbl = QLabel("Select a Pokémon")
        self.mon_name_lbl.setFont(QFont("Arial", 20, QFont.Bold))
        self.mon_name_lbl.setStyleSheet("color: #FFFFFF;")
        card_layout.addWidget(self.mon_name_lbl)

        self.type_badges_box = QHBoxLayout()
        card_layout.addLayout(self.type_badges_box)
        card_layout.addStretch()

        self.catch_rate_lbl = QLabel("")
        self.catch_rate_lbl.setStyleSheet("color: #A8A8B3; font-size: 13px; font-weight: bold;")
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
        self.bst_lbl.setStyleSheet("color: #00B37E; font-weight: bold; margin-top: 4px;")
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
            self.mon_list.addItem(f"#{pid:04d} {name}")

        if self.mon_list.count() > 0:
            self.mon_list.setCurrentRow(284) # Breloom / Shroomish default

    def filter_pokemon_list(self, text):
        query = text.strip().lower()
        self.mon_list.clear()
        for pid, name in self.all_pokemon:
            if query in name.lower() or query in str(pid):
                self.mon_list.addItem(f"#{pid:04d} {name}")
        if self.mon_list.count() > 0:
            self.mon_list.setCurrentRow(0)

    def on_pokemon_selected(self, row):
        if row < 0: return
        item = self.mon_list.item(row)
        if not item: return
        pid = int(item.text().split()[0].replace("#", ""))

        self.cur.execute("SELECT name, hp, atk, def, spa, spd, spe, bst, type1, type2, catch_rate FROM pokemon WHERE id=?", (pid,))
        row_data = self.cur.fetchone()
        if not row_data: return

        name, hp, atk, df, spa, spd, spe, bst, t1, t2, cr = row_data

        self.mon_name_lbl.setText(f"#{pid:04d} {name}")
        self.catch_rate_lbl.setText(f"Catch Rate: {cr} / 255")

        # Clear type badges
        while self.type_badges_box.count():
            item = self.type_badges_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for t in [t1, t2]:
            if t and t != "Type_0" and (t != t1 or self.type_badges_box.count() == 0):
                bg_col = TYPE_COLORS.get(t, "#444444")
                badge = QLabel(f" {t.upper()} ")
                badge.setStyleSheet(f"background-color: {bg_col}; color: white; border-radius: 4px; font-weight: bold; padding: 4px 10px;")
                self.type_badges_box.addWidget(badge)

        # Update stats
        stats_map = {"HP": hp, "Attack": atk, "Defense": df, "Sp. Atk": spa, "Sp. Def": spd, "Speed": spe}
        for s_name, val in stats_map.items():
            bar = self.stat_bars[s_name]
            bar.setValue(val)
            bar.setFormat(f"{val}")
            col = "#00B37E" if val >= 90 else ("#F7D02C" if val >= 60 else "#E25858")
            bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {col}; border-radius: 4px; }}")

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

    # ==========================================
    # TAB 2: ALL-REGION ENCOUNTERS
    # ==========================================
    def create_encounters_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # Filters Box
        filter_box = QHBoxLayout()
        filter_box.setSpacing(10)

        filter_box.addWidget(QLabel("Region:"))
        self.region_combo = QComboBox()
        self.region_combo.addItems(["All Regions", "Hoenn", "Kanto", "Sevii Islands"])
        self.region_combo.currentIndexChanged.connect(self.search_encounters)
        filter_box.addWidget(self.region_combo)

        filter_box.addWidget(QLabel("Method:"))
        self.method_combo = QComboBox()
        self.method_combo.addItems(["All Methods", "Tall Grass", "Surfing", "Fishing (Old Rod)", "Fishing (Good Rod)", "Fishing (Super Rod)", "Rock Smash"])
        self.method_combo.currentIndexChanged.connect(self.search_encounters)
        filter_box.addWidget(self.method_combo)

        filter_box.addWidget(QLabel("Search Location or Pokémon:"))
        self.enc_search = QLineEdit()
        self.enc_search.setPlaceholderText("e.g. Route 101, Petalburg, Shroomish, Pikachu...")
        self.enc_search.textChanged.connect(self.search_encounters)
        filter_box.addWidget(self.enc_search)

        layout.addLayout(filter_box)

        # Encounter Results Table
        self.enc_table = QTableWidget()
        self.enc_table.setColumnCount(8)
        self.enc_table.setHorizontalHeaderLabels([
            "Region", "Location", "Method", "Slot", "Rate %", "Level Range", "Dex #", "Pokémon"
        ])
        self.enc_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.enc_table)

        self.tabs.addTab(tab, "🗺️ Wild Encounter Maps")
        self.search_encounters()

    def search_encounters(self):
        region = self.region_combo.currentText()
        method = self.method_combo.currentText()
        query = self.enc_search.text().strip().lower()

        sql = "SELECT region, location_name, method, slot, chance, min_level, max_level, species_id, species_name FROM encounters WHERE 1=1"
        params = []

        if region != "All Regions":
            sql += " AND region = ?"
            params.append(region)
        if method != "All Methods":
            sql += " AND method = ?"
            params.append(method)
        if query:
            sql += " AND (LOWER(location_name) LIKE ? OR LOWER(species_name) LIKE ?)"
            params.extend([f"%{query}%", f"%{query}%"])

        sql += " ORDER BY region, location_name, method, slot LIMIT 300"

        self.cur.execute(sql, params)
        rows = self.cur.fetchall()

        self.enc_table.setRowCount(len(rows))
        for r_idx, (reg, loc, meth, slot, ch, min_l, max_l, sp_id, sp_name) in enumerate(rows):
            lv_txt = f"Lv. {min_l}" if min_l == max_l else f"Lv. {min_l}–{max_l}"
            self.enc_table.setItem(r_idx, 0, QTableWidgetItem(reg))
            self.enc_table.setItem(r_idx, 1, QTableWidgetItem(loc))
            self.enc_table.setItem(r_idx, 2, QTableWidgetItem(meth))
            self.enc_table.setItem(r_idx, 3, QTableWidgetItem(f"Slot {slot}"))
            self.enc_table.setItem(r_idx, 4, QTableWidgetItem(f"{ch}%"))
            self.enc_table.setItem(r_idx, 5, QTableWidgetItem(lv_txt))
            self.enc_table.setItem(r_idx, 6, QTableWidgetItem(f"#{sp_id}"))
            self.enc_table.setItem(r_idx, 7, QTableWidgetItem(sp_name))

    # ==========================================
    # TAB 3: LEGENDARY & MYTHICAL HUB
    # ==========================================
    def create_legendaries_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # Filter
        top_box = QHBoxLayout()
        top_box.addWidget(QLabel("Generation:"))
        self.leg_gen_combo = QComboBox()
        self.leg_gen_combo.addItems([
            "All Generations", "Hoenn Native", "Generation 1 (Kanto)", "Generation 2 (Johto)",
            "Generation 4 (Sinnoh)", "Generation 5 (Unova)", "Generation 6 (Kalos)",
            "Generation 7 (Alola)", "Generation 8 (Galar & Hisui)", "Generation 9 (Paldea & Paradox)"
        ])
        self.leg_gen_combo.currentIndexChanged.connect(self.filter_legendaries)
        top_box.addWidget(self.leg_gen_combo)

        top_box.addWidget(QLabel("Search Legendary:"))
        self.leg_search = QLineEdit()
        self.leg_search.setPlaceholderText("e.g. Rayquaza, Arceus, Mewtwo, Kyogre...")
        self.leg_search.textChanged.connect(self.filter_legendaries)
        top_box.addWidget(self.leg_search)

        layout.addLayout(top_box)

        # Table
        self.leg_table = QTableWidget()
        self.leg_table.setColumnCount(4)
        self.leg_table.setHorizontalHeaderLabels(["Legendary", "Generation", "Location / Level", "Requirements & Synergy Setup"])
        self.leg_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.leg_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.leg_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.leg_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        layout.addWidget(self.leg_table)

        self.tabs.addTab(tab, "⚔️ Legendary & Mythical Guide")
        self.filter_legendaries()

    def filter_legendaries(self):
        gen = self.leg_gen_combo.currentText()
        query = self.leg_search.text().strip().lower()

        sql = "SELECT name, generation, location, requirements FROM legendaries WHERE 1=1"
        params = []

        if gen != "All Generations":
            sql += " AND generation LIKE ?"
            params.append(f"%{gen.split('(')[0].strip()}%")
        if query:
            sql += " AND (LOWER(name) LIKE ? OR LOWER(location) LIKE ? OR LOWER(requirements) LIKE ?)"
            params.extend([f"%{query}%", f"%{query}%", f"%{query}%"])

        sql += " ORDER BY generation, name"
        self.cur.execute(sql, params)
        rows = self.cur.fetchall()

        self.leg_table.setRowCount(len(rows))
        for r_idx, (name, g, loc, req) in enumerate(rows):
            self.leg_table.setItem(r_idx, 0, QTableWidgetItem(name))
            self.leg_table.setItem(r_idx, 1, QTableWidgetItem(g))
            self.leg_table.setItem(r_idx, 2, QTableWidgetItem(loc))
            self.leg_table.setItem(r_idx, 3, QTableWidgetItem(req))

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
        self.calc_hp_spin.setValue(1) # Default 1 HP from False Swipe!
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
        if idx < 0: return
        pid = self.calc_mon_combo.currentData()

        self.cur.execute("SELECT hp, catch_rate FROM pokemon WHERE id=?", (pid,))
        row = self.cur.fetchone()
        if not row: return
        base_hp, cr = row

        # HP factor
        hp_pct = self.calc_hp_spin.value() / 100.0

        # Status bonus
        st_idx = self.calc_status_combo.currentIndex()
        st_mult = 2.5 if st_idx == 0 else (1.5 if st_idx == 1 else 1.0)

        # Multipliers
        multipliers = {
            "Quick": 5.0,
            "Timer": 4.0,
            "Repeat": 3.5,
            "Dusk": 3.0,
            "Ultra": 2.0,
            "Great": 1.5,
            "Poke": 1.0
        }

        # Gen 3-4 catch rate formula: a = ((3 * MaxHP - 2 * CurrentHP) * Rate * BallMult * StatusMult) / (3 * MaxHP)
        # Simplified: a = ((3 - 2 * hp_pct) * cr * ball_mult * st_mult) / 3
        for key, mult in multipliers.items():
            a = ((3.0 - 2.0 * hp_pct) * cr * mult * st_mult) / 3.0
            if a >= 255:
                prob = 100.0
            else:
                # Shake check: b = 65536 * (a / 255)^0.75
                # Capture prob = (b / 65536)^4
                p_shake = (a / 255.0) ** 0.75
                prob = (p_shake ** 4) * 100.0

            prob = min(100.0, max(0.0, prob))
            bar = self.ball_bars[key]
            bar.setValue(int(prob))
            bar.setFormat(f"{prob:.1f}%")
            col = "#00B37E" if prob >= 70 else ("#F7D02C" if prob >= 35 else "#E25858")
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
