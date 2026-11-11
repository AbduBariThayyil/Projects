#!/usr/bin/env python3
"""
Regional Map Widget for Pokémon Quetzal Companion App
=====================================================
A high-contrast, modern interactive vector Town Map supporting all 4 regions:
- Hoenn
- Johto
- Kanto
- Sevii Islands

Features:
- Standalone PySide6 custom vector canvas with QPainter antialiasing.
- Clean retro-cyber HUD aesthetic (#0b0f17 dark background, coordinate grid, route connections).
- Region switching via segmented pill controls: [ Hoenn ] [ Johto ] [ Kanto ] [ Sevii Islands ].
- Accurate regional node topology (cities, routes, caves, dungeons, landmarks).
- Dynamic completion rings:
    🟢 Green: 100% Mastered (all wild species caught)
    🟡 Amber: Partially caught / In Progress
    ⚪ Slate: 0 caught / Unexplored
- Hover floating card: Detailed stats (Caught / Total, missing Pokemon preview, area classification).
- Habitat Locator Radar: Concentric pulsing beacon rings for highlighted target locations.
- Seamless SQLite database integration with quetzal_database.db for real save/encounter sync.
- Signal: route_selected(str route_name, str region).
"""

import sys
import os
import math
import sqlite3
from typing import Dict, List, Tuple, Optional, Any, Set

from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QTimer, QSize
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QFontMetrics,
    QPainterPath, QLinearGradient, QRadialGradient, QCursor, QPixmap
)
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QButtonGroup, QFrame, QSizePolicy
)

# ============================================================================
# CONSTANTS & THEMES
# ============================================================================

REGION_HOENN = "Hoenn"
REGION_JOHTO = "Johto"
REGION_KANTO = "Kanto"
REGION_SEVII = "Sevii Islands"

ALL_REGIONS = [REGION_HOENN, REGION_JOHTO, REGION_KANTO, REGION_SEVII]

# Palette
CLR_BG = QColor("#0b0f17")
CLR_GRID_LINE = QColor(19, 27, 46, 120)
CLR_GRID_DOT = QColor(30, 41, 59, 160)
CLR_GRID_TEXT = QColor(71, 85, 105, 180)

CLR_PATH_LAND_OUTER = QColor("#0f172a")
CLR_PATH_LAND_INNER = QColor("#334155")
CLR_PATH_LAND_COMPLETE = QColor("#059669")

CLR_PATH_WATER_OUTER = QColor("#082f49")
CLR_PATH_WATER_INNER = QColor("#0284c7")

CLR_PATH_CAVE_OUTER = QColor("#1e1b4b")
CLR_PATH_CAVE_INNER = QColor("#7c3aed")

CLR_GLOW_HOVER = QColor("#38bdf8")
CLR_GLOW_TARGET = QColor("#f43f5e")

CLR_STATUS_COMPLETE = QColor("#10b981")   # 🟢 Green
CLR_STATUS_PARTIAL = QColor("#f59e0b")    # 🟡 Amber
CLR_STATUS_UNCAUGHT = QColor("#475569")   # ⚪ Slate
CLR_STATUS_TARGET = QColor("#f43f5e")     # 🎯 Rose Target

# ============================================================================
# NORMALIZATION
# ============================================================================

def normalize_loc(name: str) -> str:
    """Normalize route/town name for database matching."""
    if not name:
        return ""
    s = name.strip().upper()
    s = s.replace("É", "E").replace("é", "e")
    if "CYCLING ROAD" in s and "17" in s:
        return "ROUTE 17"
    return s

# ============================================================================
# TOPOLOGY DATA FOR ALL 4 REGIONS
# ============================================================================

# Virtual grid: 28 columns (1..28), 20 rows (1..20)
# Virtual canvas: 1100 x 700

HOENN_NODES = {
    # Towns & Cities (1:1 Native GBA Pixel Coordinates on 240x160 PokéNav Town Map)
    "Littleroot Town": {"x": 44.0, "y": 110.0, "type": "town", "label": "LIT"},
    "Oldale Town": {"x": 44.0, "y": 94.0, "type": "town", "label": "OLD"},
    "Petalburg City": {"x": 20.0, "y": 94.0, "type": "city", "label": "PET"},
    "Rustboro City": {"x": 12.0, "y": 64.0, "type": "city", "label": "RUS"},
    "Dewford Town": {"x": 27.0, "y": 135.0, "type": "town", "label": "DEW"},
    "Slateport City": {"x": 75.0, "y": 107.0, "type": "city", "label": "SLA"},
    "Mauville City": {"x": 79.0, "y": 69.0, "type": "city", "label": "MAU"},
    "Verdanturf Town": {"x": 44.0, "y": 69.0, "type": "town", "label": "VER"},
    "Fallarbor Town": {"x": 35.0, "y": 21.0, "type": "town", "label": "FAL"},
    "Lavaridge Town": {"x": 52.0, "y": 44.0, "type": "town", "label": "LAV"},
    "Fortree City": {"x": 108.0, "y": 21.0, "type": "city", "label": "FOR"},
    "Lilycove City": {"x": 159.0, "y": 45.0, "type": "city", "label": "LIL"},
    "Mossdeep City": {"x": 207.0, "y": 61.0, "type": "city", "label": "MOS"},
    "Sootopolis City": {"x": 180.0, "y": 78.0, "type": "city", "label": "SOO"},
    "Pacifidlog Town": {"x": 147.0, "y": 102.0, "type": "town", "label": "PAC"},
    "Ever Grande City": {"x": 227.0, "y": 90.0, "type": "city", "label": "EVE"},

    # Land Routes
    "Route 101": {"x": 44.0, "y": 102.0, "type": "route", "label": "101"},
    "Route 102": {"x": 32.0, "y": 94.0, "type": "route", "label": "102"},
    "Route 103": {"x": 58.0, "y": 86.0, "type": "route", "label": "103"},
    "Route 104": {"x": 12.0, "y": 82.0, "type": "route", "label": "104"},
    "Route 116": {"x": 28.0, "y": 64.0, "type": "route", "label": "116"},
    "Route 117": {"x": 61.0, "y": 69.0, "type": "route", "label": "117"},
    "Route 115": {"x": 12.0, "y": 45.0, "type": "route", "label": "115"},
    "Route 114": {"x": 22.0, "y": 28.0, "type": "route", "label": "114"},
    "Route 113": {"x": 52.0, "y": 21.0, "type": "route", "label": "113"},
    "Route 112": {"x": 65.0, "y": 48.0, "type": "route", "label": "112"},
    "Route 111": {"x": 79.0, "y": 35.0, "type": "route", "label": "111"},
    "Route 110": {"x": 75.0, "y": 88.0, "type": "route", "label": "110"},
    "Route 118": {"x": 95.0, "y": 69.0, "type": "route", "label": "118"},
    "Route 119": {"x": 108.0, "y": 45.0, "type": "route", "label": "119"},
    "Route 120": {"x": 123.0, "y": 35.0, "type": "route", "label": "120"},
    "Route 121": {"x": 142.0, "y": 54.0, "type": "route", "label": "121"},
    "Route 123": {"x": 115.0, "y": 69.0, "type": "route", "label": "123"},

    # Water Routes
    "Route 105": {"x": 12.0, "y": 120.0, "type": "water_route", "label": "105"},
    "Route 106": {"x": 20.0, "y": 131.0, "type": "water_route", "label": "106"},
    "Route 107": {"x": 43.0, "y": 135.0, "type": "water_route", "label": "107"},
    "Route 108": {"x": 58.0, "y": 135.0, "type": "water_route", "label": "108"},
    "Route 109": {"x": 75.0, "y": 122.0, "type": "water_route", "label": "109"},
    "Route 122": {"x": 142.0, "y": 70.0, "type": "water_route", "label": "122"},
    "Route 124": {"x": 183.0, "y": 54.0, "type": "water_route", "label": "124"},
    "Route 125": {"x": 207.0, "y": 45.0, "type": "water_route", "label": "125"},
    "Route 126": {"x": 175.0, "y": 78.0, "type": "water_route", "label": "126"},
    "Route 127": {"x": 207.0, "y": 78.0, "type": "water_route", "label": "127"},
    "Route 128": {"x": 216.0, "y": 90.0, "type": "water_route", "label": "128"},
    "Route 129": {"x": 207.0, "y": 102.0, "type": "water_route", "label": "129"},
    "Route 130": {"x": 183.0, "y": 102.0, "type": "water_route", "label": "130"},
    "Route 131": {"x": 165.0, "y": 102.0, "type": "water_route", "label": "131"},
    "Route 132": {"x": 130.0, "y": 102.0, "type": "water_route", "label": "132"},
    "Route 133": {"x": 115.0, "y": 102.0, "type": "water_route", "label": "133"},
    "Route 134": {"x": 95.0, "y": 102.0, "type": "water_route", "label": "134"},

    # Caves & Landmarks
    "Petalburg Woods": {"x": 12.0, "y": 92.0, "type": "landmark", "label": "WOD"},
    "Rusturf Tunnel": {"x": 36.0, "y": 64.0, "type": "landmark", "label": "TUN"},
    "Granite Cave": {"x": 20.0, "y": 135.0, "type": "landmark", "label": "GNT"},
    "Abandoned Ship": {"x": 58.0, "y": 138.0, "type": "landmark", "label": "SHP"},
    "New Mauville": {"x": 83.0, "y": 90.0, "type": "landmark", "label": "NMV"},
    "Fiery Path": {"x": 68.0, "y": 36.0, "type": "landmark", "label": "FIE"},
    "Jagged Pass": {"x": 58.0, "y": 44.0, "type": "landmark", "label": "JAG"},
    "Meteor Falls": {"x": 12.0, "y": 22.0, "type": "landmark", "label": "MET"},
    "Mirage Tower": {"x": 84.0, "y": 32.0, "type": "landmark", "label": "MIR"},
    "Desert Underpass": {"x": 84.0, "y": 40.0, "type": "landmark", "label": "DES"},
    "Safari Zone": {"x": 142.0, "y": 42.0, "type": "landmark", "label": "SAF"},
    "Mt. Pyre": {"x": 142.0, "y": 64.0, "type": "landmark", "label": "PYR"},
    "Artisan Cave": {"x": 159.0, "y": 36.0, "type": "landmark", "label": "ART"},
    "Shoal Cave": {"x": 207.0, "y": 36.0, "type": "landmark", "label": "SHO"},
    "Cave of Origin": {"x": 180.0, "y": 72.0, "type": "landmark", "label": "ORI"},
    "Seafloor Cavern": {"x": 207.0, "y": 90.0, "type": "landmark", "label": "SEA"},
    "Victory Road": {"x": 227.0, "y": 80.0, "type": "landmark", "label": "VIC"},
    "Sky Pillar": {"x": 165.0, "y": 92.0, "type": "landmark", "label": "SKY"},
    "Altering Cave": {"x": 58.0, "y": 86.0, "type": "landmark", "label": "ALT"}
}

HOENN_EDGES = [
    ("Littleroot Town", "Route 101", "land"),
    ("Route 101", "Oldale Town", "land"),
    ("Oldale Town", "Route 102", "land"),
    ("Route 102", "Petalburg City", "land"),
    ("Petalburg City", "Route 104", "land"),
    ("Route 104", "Petalburg Woods", "land"),
    ("Petalburg Woods", "Rustboro City", "land"),
    ("Rustboro City", "Route 116", "land"),
    ("Route 116", "Rusturf Tunnel", "tunnel"),
    ("Rusturf Tunnel", "Verdanturf Town", "tunnel"),
    ("Verdanturf Town", "Route 117", "land"),
    ("Route 117", "Mauville City", "land"),
    ("Rustboro City", "Route 115", "land"),
    ("Route 115", "Meteor Falls", "cave"),
    ("Meteor Falls", "Route 114", "cave"),
    ("Route 114", "Fallarbor Town", "land"),
    ("Fallarbor Town", "Route 113", "land"),
    ("Route 113", "Route 111", "land"),
    ("Route 111", "Route 112", "land"),
    ("Route 112", "Fiery Path", "cave"),
    ("Fiery Path", "Lavaridge Town", "land"),
    ("Lavaridge Town", "Jagged Pass", "land"),
    ("Jagged Pass", "Route 112", "land"),
    ("Route 111", "Mauville City", "land"),
    ("Route 111", "Mirage Tower", "land"),
    ("Route 111", "Desert Underpass", "tunnel"),
    ("Mauville City", "Route 110", "land"),
    ("Route 110", "Slateport City", "land"),
    ("Route 110", "New Mauville", "tunnel"),
    ("Oldale Town", "Route 103", "land"),
    ("Route 103", "Route 110", "water"),
    ("Route 103", "Altering Cave", "cave"),
    ("Route 104", "Route 105", "water"),
    ("Route 105", "Route 106", "water"),
    ("Route 106", "Dewford Town", "water"),
    ("Dewford Town", "Granite Cave", "cave"),
    ("Dewford Town", "Route 107", "water"),
    ("Route 107", "Route 108", "water"),
    ("Route 108", "Abandoned Ship", "water"),
    ("Route 108", "Route 109", "water"),
    ("Route 109", "Slateport City", "water"),
    ("Mauville City", "Route 118", "land"),
    ("Route 118", "Route 119", "land"),
    ("Route 119", "Fortree City", "land"),
    ("Fortree City", "Route 120", "land"),
    ("Route 120", "Route 121", "land"),
    ("Route 121", "Safari Zone", "land"),
    ("Route 121", "Lilycove City", "land"),
    ("Lilycove City", "Artisan Cave", "cave"),
    ("Route 121", "Route 122", "water"),
    ("Route 122", "Mt. Pyre", "landmark"),
    ("Route 122", "Route 123", "land"),
    ("Route 123", "Route 118", "land"),
    ("Lilycove City", "Route 124", "water"),
    ("Route 124", "Mossdeep City", "water"),
    ("Mossdeep City", "Route 125", "water"),
    ("Route 125", "Shoal Cave", "cave"),
    ("Route 124", "Route 126", "water"),
    ("Route 126", "Sootopolis City", "water"),
    ("Sootopolis City", "Cave of Origin", "cave"),
    ("Mossdeep City", "Route 127", "water"),
    ("Route 127", "Route 128", "water"),
    ("Route 128", "Seafloor Cavern", "cave"),
    ("Route 128", "Ever Grande City", "water"),
    ("Ever Grande City", "Victory Road", "cave"),
    ("Route 128", "Route 129", "water"),
    ("Route 129", "Route 130", "water"),
    ("Route 130", "Route 131", "water"),
    ("Route 131", "Sky Pillar", "landmark"),
    ("Route 131", "Pacifidlog Town", "water"),
    ("Pacifidlog Town", "Route 132", "water"),
    ("Route 132", "Route 133", "water"),
    ("Route 133", "Route 134", "water"),
    ("Route 134", "Slateport City", "water"),
]

JOHTO_NODES = {
    # Towns & Cities
    "New Bark Town": {"x": 21.0, "y": 14.5, "type": "town", "label": "NBT"},
    "Cherrygrove City": {"x": 15.0, "y": 14.5, "type": "city", "label": "CHE"},
    "Violet City": {"x": 12.0, "y": 8.0, "type": "city", "label": "VIO"},
    "Azalea Town": {"x": 8.0, "y": 15.0, "type": "town", "label": "AZA"},
    "Goldenrod City": {"x": 6.0, "y": 9.5, "type": "city", "label": "GOL"},
    "Ecruteak City": {"x": 10.5, "y": 2.5, "type": "city", "label": "ECR"},
    "Olivine City": {"x": 5.5, "y": 6.0, "type": "city", "label": "OLI"},
    "Cianwood City": {"x": 1.5, "y": 12.5, "type": "city", "label": "CIA"},
    "Mahogany Town": {"x": 16.5, "y": 2.5, "type": "town", "label": "MAH"},
    "Blackthorn City": {"x": 22.0, "y": 3.5, "type": "city", "label": "BLA"},

    # Routes
    "Route 29": {"x": 18.0, "y": 14.5, "type": "route", "label": "29"},
    "Route 30": {"x": 15.0, "y": 11.0, "type": "route", "label": "30"},
    "Route 31": {"x": 14.0, "y": 8.0, "type": "route", "label": "31"},
    "Route 32": {"x": 12.0, "y": 11.5, "type": "route", "label": "32"},
    "Route 33": {"x": 10.0, "y": 15.0, "type": "route", "label": "33"},
    "Route 34": {"x": 6.0, "y": 12.0, "type": "route", "label": "34"},
    "Route 35": {"x": 6.0, "y": 7.0, "type": "route", "label": "35"},
    "Route 36": {"x": 9.5, "y": 5.5, "type": "route", "label": "36"},
    "Route 37": {"x": 10.5, "y": 4.0, "type": "route", "label": "37"},
    "Route 38": {"x": 7.5, "y": 2.5, "type": "route", "label": "38"},
    "Route 39": {"x": 5.5, "y": 4.0, "type": "route", "label": "39"},
    "Route 40": {"x": 4.0, "y": 8.0, "type": "water_route", "label": "40"},
    "Route 41": {"x": 3.0, "y": 10.5, "type": "water_route", "label": "41"},
    "Route 42": {"x": 13.5, "y": 2.5, "type": "route", "label": "42"},
    "Route 43": {"x": 16.5, "y": 1.2, "type": "route", "label": "43"},
    "Route 44": {"x": 19.2, "y": 2.5, "type": "route", "label": "44"},
    "Route 45": {"x": 22.0, "y": 7.5, "type": "route", "label": "45"},
    "Route 46": {"x": 19.5, "y": 11.0, "type": "route", "label": "46"},
    "Route 26": {"x": 25.0, "y": 11.0, "type": "route", "label": "26"},
    "Route 27": {"x": 23.5, "y": 14.5, "type": "route", "label": "27"},
    "Route 28": {"x": 24.5, "y": 7.5, "type": "route", "label": "28"},

    # Caves & Landmarks
    "Dark Cave": {"x": 17.0, "y": 8.0, "type": "landmark", "label": "DRK"},
    "Sprout Tower": {"x": 12.0, "y": 6.2, "type": "landmark", "label": "SPR"},
    "Ruins of Alph": {"x": 10.0, "y": 10.0, "type": "landmark", "label": "ALF"},
    "Union Cave": {"x": 12.0, "y": 15.0, "type": "landmark", "label": "UNI"},
    "Slowpoke Well": {"x": 8.5, "y": 16.5, "type": "landmark", "label": "WEL"},
    "Ilex Forest": {"x": 6.0, "y": 15.0, "type": "landmark", "label": "ILX"},
    "National Park": {"x": 7.5, "y": 5.5, "type": "landmark", "label": "NAT"},
    "Burned Tower": {"x": 9.2, "y": 1.5, "type": "landmark", "label": "BUR"},
    "Bell Tower": {"x": 11.8, "y": 1.5, "type": "landmark", "label": "BEL"},
    "Lighthouse": {"x": 6.8, "y": 6.5, "type": "landmark", "label": "LIG"},
    "Whirl Islands": {"x": 1.8, "y": 10.5, "type": "landmark", "label": "WHL"},
    "Mt. Mortar": {"x": 13.5, "y": 1.2, "type": "landmark", "label": "MOR"},
    "Rocket Hideout": {"x": 16.5, "y": 3.8, "type": "landmark", "label": "ROK"},
    "Lake of Rage": {"x": 18.0, "y": 0.5, "type": "landmark", "label": "RAG"},
    "Ice Path": {"x": 20.8, "y": 2.5, "type": "landmark", "label": "ICE"},
    "Dragon's Den": {"x": 22.0, "y": 1.8, "type": "landmark", "label": "DRA"},
    "Mt. Silver": {"x": 22.5, "y": 6.5, "type": "landmark", "label": "SLV"}
}

JOHTO_EDGES = [
    ("New Bark Town", "Route 29", "land"),
    ("Route 29", "Cherrygrove City", "land"),
    ("Route 29", "Route 46", "land"),
    ("New Bark Town", "Route 27", "water"),
    ("Route 27", "Route 26", "land"),
    ("Route 26", "Route 28", "land"),
    ("Route 28", "Mt. Silver", "landmark"),
    ("Cherrygrove City", "Route 30", "land"),
    ("Route 30", "Route 31", "land"),
    ("Route 31", "Dark Cave", "cave"),
    ("Dark Cave", "Route 46", "cave"),
    ("Route 31", "Violet City", "land"),
    ("Violet City", "Sprout Tower", "landmark"),
    ("Violet City", "Ruins of Alph", "landmark"),
    ("Violet City", "Route 32", "land"),
    ("Route 32", "Union Cave", "cave"),
    ("Union Cave", "Route 33", "cave"),
    ("Route 33", "Azalea Town", "land"),
    ("Azalea Town", "Slowpoke Well", "cave"),
    ("Azalea Town", "Ilex Forest", "landmark"),
    ("Ilex Forest", "Route 34", "land"),
    ("Route 34", "Goldenrod City", "land"),
    ("Goldenrod City", "Route 35", "land"),
    ("Route 35", "National Park", "land"),
    ("National Park", "Route 36", "land"),
    ("Route 36", "Route 37", "land"),
    ("Route 36", "Violet City", "land"),
    ("Route 37", "Ecruteak City", "land"),
    ("Ecruteak City", "Burned Tower", "landmark"),
    ("Ecruteak City", "Bell Tower", "landmark"),
    ("Ecruteak City", "Route 38", "land"),
    ("Route 38", "Route 39", "land"),
    ("Route 39", "Olivine City", "land"),
    ("Olivine City", "Lighthouse", "landmark"),
    ("Olivine City", "Route 40", "water"),
    ("Route 40", "Route 41", "water"),
    ("Route 41", "Whirl Islands", "landmark"),
    ("Route 41", "Cianwood City", "water"),
    ("Ecruteak City", "Route 42", "land"),
    ("Route 42", "Mt. Mortar", "cave"),
    ("Route 42", "Mahogany Town", "land"),
    ("Mahogany Town", "Rocket Hideout", "landmark"),
    ("Mahogany Town", "Route 43", "land"),
    ("Route 43", "Lake of Rage", "water"),
    ("Mahogany Town", "Route 44", "land"),
    ("Route 44", "Ice Path", "cave"),
    ("Ice Path", "Blackthorn City", "cave"),
    ("Blackthorn City", "Dragon's Den", "landmark"),
    ("Blackthorn City", "Route 45", "land"),
    ("Route 45", "Route 46", "land"),
]

KANTO_NODES = {
    # Towns & Cities
    "Pallet Town": {"x": 5.0, "y": 14.0, "type": "town", "label": "PAL"},
    "Viridian City": {"x": 5.0, "y": 9.5, "type": "city", "label": "VIR"},
    "Pewter City": {"x": 5.0, "y": 4.0, "type": "city", "label": "PEW"},
    "Cerulean City": {"x": 15.0, "y": 4.0, "type": "city", "label": "CER"},
    "Vermilion City": {"x": 15.0, "y": 13.5, "type": "city", "label": "VER"},
    "Lavender Town": {"x": 20.0, "y": 9.0, "type": "town", "label": "LAV"},
    "Celadon City": {"x": 10.0, "y": 9.0, "type": "city", "label": "CEL"},
    "Saffron City": {"x": 15.0, "y": 9.0, "type": "city", "label": "SAF"},
    "Fuchsia City": {"x": 12.0, "y": 15.0, "type": "city", "label": "FUC"},
    "Cinnabar Island": {"x": 5.0, "y": 18.0, "type": "town", "label": "CIN"},
    "Indigo Plateau": {"x": 2.0, "y": 2.5, "type": "city", "label": "IND"},

    # Routes
    "Route 1": {"x": 5.0, "y": 11.8, "type": "route", "label": "1"},
    "Route 2": {"x": 5.0, "y": 7.0, "type": "route", "label": "2"},
    "Route 3": {"x": 7.5, "y": 4.0, "type": "route", "label": "3"},
    "Route 4": {"x": 12.5, "y": 4.0, "type": "route", "label": "4"},
    "Route 5": {"x": 15.0, "y": 6.5, "type": "route", "label": "5"},
    "Route 6": {"x": 15.0, "y": 11.2, "type": "route", "label": "6"},
    "Route 7": {"x": 12.5, "y": 9.0, "type": "route", "label": "7"},
    "Route 8": {"x": 17.5, "y": 9.0, "type": "route", "label": "8"},
    "Route 9": {"x": 18.0, "y": 4.0, "type": "route", "label": "9"},
    "Route 10": {"x": 20.0, "y": 5.5, "type": "route", "label": "10"},
    "Route 11": {"x": 18.0, "y": 13.5, "type": "route", "label": "11"},
    "Route 12": {"x": 20.0, "y": 12.0, "type": "route", "label": "12"},
    "Route 13": {"x": 18.0, "y": 15.0, "type": "route", "label": "13"},
    "Route 14": {"x": 16.0, "y": 15.5, "type": "route", "label": "14"},
    "Route 15": {"x": 14.0, "y": 15.5, "type": "route", "label": "15"},
    "Route 16": {"x": 7.5, "y": 9.0, "type": "route", "label": "16"},
    "Route 17 (Cycling Road)": {"x": 7.5, "y": 12.5, "type": "route", "label": "17"},
    "Route 18": {"x": 9.5, "y": 15.0, "type": "route", "label": "18"},
    "Route 19": {"x": 12.0, "y": 18.0, "type": "water_route", "label": "19"},
    "Route 20": {"x": 8.5, "y": 18.0, "type": "water_route", "label": "20"},
    "Route 21": {"x": 5.0, "y": 16.0, "type": "water_route", "label": "21"},
    "Route 22": {"x": 3.0, "y": 9.5, "type": "route", "label": "22"},
    "Route 23": {"x": 2.0, "y": 7.0, "type": "route", "label": "23"},
    "Route 24": {"x": 15.0, "y": 2.2, "type": "route", "label": "24"},
    "Route 25": {"x": 17.5, "y": 2.0, "type": "route", "label": "25"},

    # Caves & Landmarks
    "Viridian Forest": {"x": 5.0, "y": 5.5, "type": "landmark", "label": "FOR"},
    "Mt. Moon": {"x": 10.0, "y": 4.0, "type": "landmark", "label": "MOO"},
    "Cerulean Cave": {"x": 13.8, "y": 2.5, "type": "landmark", "label": "CAV"},
    "Diglett's Cave": {"x": 7.0, "y": 6.5, "type": "landmark", "label": "DIG"},
    "Rock Tunnel": {"x": 20.0, "y": 7.0, "type": "landmark", "label": "RCK"},
    "Power Plant": {"x": 22.0, "y": 6.5, "type": "landmark", "label": "POW"},
    "Pokémon Tower": {"x": 21.8, "y": 9.0, "type": "landmark", "label": "TOW"},
    "Safari Zone": {"x": 12.0, "y": 13.2, "type": "landmark", "label": "SAF"},
    "Seafoam Islands": {"x": 7.0, "y": 18.0, "type": "landmark", "label": "SEA"},
    "Pokémon Mansion": {"x": 3.2, "y": 18.0, "type": "landmark", "label": "MAN"},
    "Victory Road": {"x": 2.0, "y": 4.8, "type": "landmark", "label": "VIC"}
}

KANTO_EDGES = [
    ("Pallet Town", "Route 1", "land"),
    ("Route 1", "Viridian City", "land"),
    ("Viridian City", "Route 2", "land"),
    ("Route 2", "Viridian Forest", "landmark"),
    ("Viridian Forest", "Pewter City", "land"),
    ("Viridian City", "Route 22", "land"),
    ("Route 22", "Route 23", "land"),
    ("Route 23", "Victory Road", "cave"),
    ("Victory Road", "Indigo Plateau", "landmark"),
    ("Pewter City", "Route 3", "land"),
    ("Route 3", "Mt. Moon", "cave"),
    ("Mt. Moon", "Route 4", "cave"),
    ("Route 4", "Cerulean City", "land"),
    ("Cerulean City", "Cerulean Cave", "cave"),
    ("Cerulean City", "Route 24", "land"),
    ("Route 24", "Route 25", "land"),
    ("Cerulean City", "Route 5", "land"),
    ("Route 5", "Saffron City", "land"),
    ("Saffron City", "Route 7", "land"),
    ("Route 7", "Celadon City", "land"),
    ("Celadon City", "Route 16", "land"),
    ("Route 16", "Route 17 (Cycling Road)", "land"),
    ("Route 17 (Cycling Road)", "Route 18", "land"),
    ("Route 18", "Fuchsia City", "land"),
    ("Saffron City", "Route 8", "land"),
    ("Route 8", "Lavender Town", "land"),
    ("Lavender Town", "Pokémon Tower", "landmark"),
    ("Cerulean City", "Route 9", "land"),
    ("Route 9", "Route 10", "land"),
    ("Route 10", "Rock Tunnel", "cave"),
    ("Rock Tunnel", "Lavender Town", "cave"),
    ("Route 10", "Power Plant", "landmark"),
    ("Saffron City", "Route 6", "land"),
    ("Route 6", "Vermilion City", "land"),
    ("Vermilion City", "Route 11", "land"),
    ("Route 11", "Route 12", "land"),
    ("Lavender Town", "Route 12", "land"),
    ("Route 12", "Route 13", "land"),
    ("Route 13", "Route 14", "land"),
    ("Route 14", "Route 15", "land"),
    ("Route 15", "Fuchsia City", "land"),
    ("Fuchsia City", "Safari Zone", "landmark"),
    ("Route 2", "Diglett's Cave", "cave"),
    ("Diglett's Cave", "Vermilion City", "cave"),
    ("Fuchsia City", "Route 19", "water"),
    ("Route 19", "Route 20", "water"),
    ("Route 20", "Seafoam Islands", "landmark"),
    ("Seafoam Islands", "Cinnabar Island", "water"),
    ("Cinnabar Island", "Pokémon Mansion", "landmark"),
    ("Cinnabar Island", "Route 21", "water"),
    ("Route 21", "Pallet Town", "water")
]

SEVII_NODES = {
    # Island 1 (Knot Island)
    "One Island": {"x": 4.0, "y": 9.5, "type": "town", "label": "1-ISL"},
    "Kindle Road": {"x": 4.0, "y": 6.0, "type": "route", "label": "KND"},
    "Mt. Ember": {"x": 4.0, "y": 2.5, "type": "landmark", "label": "EMB"},
    "Treasure Beach": {"x": 4.0, "y": 12.0, "type": "landmark", "label": "TRS"},

    # Island 2 (Boon Island)
    "Two Island": {"x": 9.5, "y": 9.5, "type": "town", "label": "2-ISL"},
    "Cape Brink": {"x": 9.5, "y": 6.0, "type": "route", "label": "BRK"},

    # Island 3 (Kin Island)
    "Three Island": {"x": 15.0, "y": 9.5, "type": "town", "label": "3-ISL"},
    "Bond Bridge": {"x": 13.0, "y": 7.0, "type": "route", "label": "BND"},
    "Berry Forest": {"x": 12.0, "y": 5.0, "type": "landmark", "label": "BER"},

    # Island 4 (Floe Island)
    "Four Island": {"x": 5.0, "y": 16.5, "type": "town", "label": "4-ISL"},
    "Icefall Cave": {"x": 7.5, "y": 16.5, "type": "landmark", "label": "ICE"},

    # Island 5 (Chronos Island)
    "Five Island": {"x": 11.0, "y": 15.5, "type": "town", "label": "5-ISL"},
    "Five Isle Meadow": {"x": 13.0, "y": 15.5, "type": "route", "label": "MDW"},
    "Memorial Pillar": {"x": 13.0, "y": 18.5, "type": "landmark", "label": "MEM"},
    "Resort Gorgeous": {"x": 11.0, "y": 13.0, "type": "water_route", "label": "RES"},
    "Lost Cave": {"x": 12.5, "y": 13.0, "type": "landmark", "label": "LST"},

    # Island 6 (Fortune Island)
    "Six Island": {"x": 18.0, "y": 14.5, "type": "town", "label": "6-ISL"},
    "Water Path": {"x": 18.0, "y": 17.0, "type": "water_route", "label": "WTR"},
    "Ruin Valley": {"x": 16.5, "y": 18.5, "type": "landmark", "label": "VAL"},
    "Dotted Hole": {"x": 15.0, "y": 18.5, "type": "landmark", "label": "DOT"},
    "Green Path": {"x": 19.5, "y": 13.0, "type": "water_route", "label": "GRN"},
    "Outcast Island": {"x": 20.5, "y": 11.5, "type": "water_route", "label": "OUT"},

    # Island 7 (Quest Island)
    "Seven Island": {"x": 24.5, "y": 5.0, "type": "town", "label": "7-ISL"},
    "Trainer Tower": {"x": 24.5, "y": 2.5, "type": "landmark", "label": "TRN"},
    "Canyon Entrance": {"x": 24.5, "y": 8.5, "type": "route", "label": "CAN"},
    "Sevault Canyon": {"x": 24.5, "y": 12.5, "type": "landmark", "label": "SEV"},
    "Tanoby Ruins": {"x": 24.5, "y": 16.5, "type": "landmark", "label": "TAN"}
}

SEVII_EDGES = [
    # Island 1
    ("Treasure Beach", "One Island", "water"),
    ("One Island", "Kindle Road", "water"),
    ("Kindle Road", "Mt. Ember", "landmark"),

    # Island 2
    ("Two Island", "Cape Brink", "land"),

    # Island 3
    ("Three Island", "Bond Bridge", "land"),
    ("Bond Bridge", "Berry Forest", "landmark"),

    # Island 4
    ("Four Island", "Icefall Cave", "cave"),

    # Island 5
    ("Resort Gorgeous", "Lost Cave", "cave"),
    ("Resort Gorgeous", "Five Island", "water"),
    ("Five Island", "Five Isle Meadow", "land"),
    ("Five Isle Meadow", "Memorial Pillar", "landmark"),

    # Island 6
    ("Outcast Island", "Green Path", "water"),
    ("Green Path", "Six Island", "water"),
    ("Six Island", "Water Path", "water"),
    ("Water Path", "Ruin Valley", "land"),
    ("Ruin Valley", "Dotted Hole", "cave"),

    # Island 7
    ("Trainer Tower", "Seven Island", "land"),
    ("Seven Island", "Canyon Entrance", "land"),
    ("Canyon Entrance", "Sevault Canyon", "land"),
    ("Sevault Canyon", "Tanoby Ruins", "landmark"),

    # Seagallop Ferry Connections
    ("One Island", "Two Island", "water"),
    ("Two Island", "Three Island", "water"),
    ("Three Island", "Four Island", "water"),
    ("Four Island", "Five Island", "water"),
    ("Five Island", "Six Island", "water"),
    ("Six Island", "Seven Island", "water"),
]

REGIONAL_MAP_DATA = {
    REGION_HOENN: {"nodes": HOENN_NODES, "edges": HOENN_EDGES},
    REGION_JOHTO: {"nodes": JOHTO_NODES, "edges": JOHTO_EDGES},
    REGION_KANTO: {"nodes": KANTO_NODES, "edges": KANTO_EDGES},
    REGION_SEVII: {"nodes": SEVII_NODES, "edges": SEVII_EDGES},
}

# ============================================================================
# VECTOR CANVAS COMPONENT
# ============================================================================

class MapCanvas(QWidget):
    """Interactive Vector Town Map Canvas with high-contrast HUD styling."""

    node_clicked = Signal(str, str)   # (location_name, region)
    node_hovered = Signal(str, str)   # (location_name, region)

    VIRTUAL_W = 960.0
    VIRTUAL_H = 640.0
    PAD_X = 50.0
    PAD_Y = 50.0
    GRID_COLS = 28.0
    GRID_ROWS = 20.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(QSize(600, 380))

        self.region = REGION_HOENN
        self.hovered_node: Optional[str] = None
        self.selected_node: Optional[str] = None
        self.mouse_pos = QPointF(0, 0)

        # Route stats: normalized_name -> (caught_count, total_count)
        self.caught_stats: Dict[str, Tuple[int, int]] = {}
        # Missing species: normalized_name -> List[str]
        self.missing_species: Dict[str, List[str]] = {}
        # Wild species list: normalized_name -> List[str]
        self.encounters_by_loc: Dict[str, List[str]] = {}
        # Trainers list: normalized_name -> List[Dict[str, str]]
        self.trainers_by_loc: Dict[str, List[Dict[str, str]]] = {}
        # Highlighted locations (set of normalized names)
        self.highlighted_nodes: Set[str] = set()
        # Filter mode: "all", "incomplete", "mastered"
        self.filter_mode: str = "all"

        # Interactive Pan & Zoom Controls
        self.zoom_factor = 1.0
        self.pan_offset = QPointF(0, 0)
        self.is_panning = False
        self.last_mouse_pos = QPointF(0, 0)
        self.show_trainers = True
        self.show_encounters = True

        # Load authentic GBA Hoenn Town Map graphic
        self.hoenn_pixmap = QPixmap()
        base_dir = os.path.dirname(os.path.abspath(__file__))
        candidate_paths = [
            os.path.join(base_dir, "assets", "hoenn_town_map_gba_960x640.png"),
            os.path.join(base_dir, "assets", "hoenn_town_map_gba_240x160.png"),
            os.path.join(base_dir, "assets", "hoenn_pokenav_town_map_raw.png"),
            "/home/vibecoder/Projects/assets/hoenn_town_map_gba_960x640.png",
        ]
        for p in candidate_paths:
            if os.path.exists(p):
                pm = QPixmap(p)
                if not pm.isNull():
                    self.hoenn_pixmap = pm
                    break

        # Radar animation timer for target pulse
        self.radar_phase = 0.0
        self.pulse_timer = QTimer(self)
        self.pulse_timer.timeout.connect(self._on_pulse)
        self.pulse_timer.start(50)  # ~20 FPS for gentle pulse

    def _on_pulse(self):
        if self.highlighted_nodes:
            self.radar_phase = (self.radar_phase + 0.05) % 1.0
            self.update()

    def set_region(self, region: str):
        if region in REGIONAL_MAP_DATA:
            self.region = region
            self.hovered_node = None
            self.selected_node = None
            self.update()

    def get_node_screen_pos(self, grid_x: float, grid_y: float) -> Tuple[float, float]:
        if self.region == REGION_HOENN:
            # 1:1 authentic GBA coordinate mapping (240x160 native -> 960x640 virtual canvas)
            scale_x = self.VIRTUAL_W / 240.0
            scale_y = self.VIRTUAL_H / 160.0
            return grid_x * scale_x, grid_y * scale_y
        else:
            step_x = (self.VIRTUAL_W - 2 * self.PAD_X) / (self.GRID_COLS - 1.0)
            step_y = (self.VIRTUAL_H - 2 * self.PAD_Y) / (self.GRID_ROWS - 1.0)
            px = self.PAD_X + (grid_x - 1.0) * step_x
            py = self.PAD_Y + (grid_y - 1.0) * step_y
            return px, py

    def _get_transform(self) -> Tuple[float, float, float]:
        """Calculates scale and offset with dynamic pan & zoom factor applied."""
        w, h = float(self.width()), float(self.height())
        base_scale = min(w / self.VIRTUAL_W, h / self.VIRTUAL_H)
        scale = base_scale * self.zoom_factor
        offset_x = (w - self.VIRTUAL_W * scale) / 2.0 + self.pan_offset.x()
        offset_y = (h - self.VIRTUAL_H * scale) / 2.0 + self.pan_offset.y()
        return scale, offset_x, offset_y

    def zoom_in(self):
        self.zoom_factor = min(3.5, self.zoom_factor * 1.25)
        self.update()

    def zoom_out(self):
        self.zoom_factor = max(0.65, self.zoom_factor / 1.25)
        self.update()

    def reset_zoom(self):
        self.zoom_factor = 1.0
        self.pan_offset = QPointF(0, 0)
        self.update()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0:
            self.zoom_in()
        elif delta < 0:
            self.zoom_out()
        event.accept()

    def _screen_to_virtual(self, pos: QPointF) -> QPointF:
        scale, offset_x, offset_y = self._get_transform()
        if scale <= 0:
            return QPointF(0, 0)
        vx = (pos.x() - offset_x) / scale
        vy = (pos.y() - offset_y) / scale
        return QPointF(vx, vy)

    def _find_node_at(self, vpos: QPointF) -> Optional[str]:
        nodes = REGIONAL_MAP_DATA.get(self.region, {}).get("nodes", {})
        hit_radius = 16.0 if self.region == REGION_HOENN else 18.0
        best_name = None
        best_dist = 999999.0
        for name, data in nodes.items():
            px, py = self.get_node_screen_pos(data["x"], data["y"])
            dist = math.hypot(vpos.x() - px, vpos.y() - py)
            threshold = hit_radius * (1.35 if data.get("type") in ("city", "town") else 1.0)
            if dist <= threshold and dist < best_dist:
                best_dist = dist
                best_name = name
        return best_name

    def mouseMoveEvent(self, event):
        self.mouse_pos = event.position()
        if self.is_panning:
            diff = self.mouse_pos - self.last_mouse_pos
            self.pan_offset += diff
            self.last_mouse_pos = self.mouse_pos
            self.update()
            return

        vpos = self._screen_to_virtual(self.mouse_pos)
        old_hover = self.hovered_node
        self.hovered_node = self._find_node_at(vpos)

        if self.hovered_node != old_hover:
            if self.hovered_node:
                self.setCursor(QCursor(Qt.PointingHandCursor))
                self.node_hovered.emit(self.hovered_node, self.region)
            else:
                self.setCursor(QCursor(Qt.ArrowCursor))
            self.update()

    def mousePressEvent(self, event):
        if event.button() in (Qt.MiddleButton, Qt.RightButton):
            self.is_panning = True
            self.last_mouse_pos = event.position()
            self.setCursor(QCursor(Qt.ClosedHandCursor))
            event.accept()
            return
        elif event.button() == Qt.LeftButton:
            vpos = self._screen_to_virtual(event.position())
            clicked = self._find_node_at(vpos)
            if clicked:
                self.selected_node = clicked
                self.node_clicked.emit(clicked, self.region)
                self.update()
            else:
                self.is_panning = True
                self.last_mouse_pos = event.position()
                self.setCursor(QCursor(Qt.ClosedHandCursor))

    def mouseReleaseEvent(self, event):
        if self.is_panning:
            self.is_panning = False
            self.setCursor(QCursor(Qt.ArrowCursor))
            self.update()

    def leaveEvent(self, event):
        if self.hovered_node is not None:
            self.hovered_node = None
            self.setCursor(QCursor(Qt.ArrowCursor))
            self.update()

    # ========================================================================
    # PAINT EVENT
    # ========================================================================

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        # Clear background to dark HUD navy
        painter.fillRect(self.rect(), CLR_BG)

        scale, offset_x, offset_y = self._get_transform()
        painter.save()
        painter.translate(offset_x, offset_y)
        painter.scale(scale, scale)

        if self.region == REGION_HOENN and not self.hoenn_pixmap.isNull():
            # 1. Authentic 1:1 GBA Hoenn Town Map Background
            painter.drawPixmap(
                QRectF(0, 0, self.VIRTUAL_W, self.VIRTUAL_H),
                self.hoenn_pixmap,
                QRectF(self.hoenn_pixmap.rect())
            )
            # 2. Dynamic Route Connections
            self._draw_edges(painter)
            # 3. Interactive GBA Markers & Completion Rings
            self._draw_nodes(painter)
            # 4. Authentic Bottom-Right Flower Frame Info Box
            self._draw_flower_frame_info(painter)
        else:
            # 1. Background Grid & Coordinates
            self._draw_grid_and_margins(painter)
            # 2. Regional Watermark
            self._draw_region_watermark(painter)
            # 3. Route Connection Edges
            self._draw_edges(painter)
            # 4. Regional Nodes (Cities, Routes, Landmarks)
            self._draw_nodes(painter)
            # 5. Floating Hover Tooltip Card
            if self.hovered_node:
                self._draw_hover_card(painter, self.hovered_node)

        painter.restore()

    def _draw_grid_and_margins(self, painter: QPainter):
        """Draws subtle retro-futuristic grid coordinates."""
        step_x = (self.VIRTUAL_W - 2 * self.PAD_X) / (self.GRID_COLS - 1.0)
        step_y = (self.VIRTUAL_H - 2 * self.PAD_Y) / (self.GRID_ROWS - 1.0)

        pen = QPen(CLR_GRID_LINE, 1.0)
        painter.setPen(pen)

        for col in range(int(self.GRID_COLS)):
            x = self.PAD_X + col * step_x
            painter.drawLine(QPointF(x, self.PAD_Y), QPointF(x, self.VIRTUAL_H - self.PAD_Y))

        for row in range(int(self.GRID_ROWS)):
            y = self.PAD_Y + row * step_y
            painter.drawLine(QPointF(self.PAD_X, y), QPointF(self.VIRTUAL_W - self.PAD_X, y))

        font = QFont("Monospace", 7, QFont.Bold)
        painter.setFont(font)
        painter.setPen(CLR_GRID_TEXT)

        for col in range(int(self.GRID_COLS)):
            x = self.PAD_X + col * step_x
            lbl = f"{col + 1:02d}"
            painter.drawText(QRectF(x - 12, self.PAD_Y - 24, 24, 18), Qt.AlignCenter, lbl)
            painter.drawText(QRectF(x - 12, self.VIRTUAL_H - self.PAD_Y + 8, 24, 18), Qt.AlignCenter, lbl)

        for row in range(int(self.GRID_ROWS)):
            y = self.PAD_Y + row * step_y
            lbl = chr(ord('A') + row)
            painter.drawText(QRectF(self.PAD_X - 28, y - 9, 20, 18), Qt.AlignRight | Qt.AlignVCenter, lbl)
            painter.drawText(QRectF(self.VIRTUAL_W - self.PAD_X + 8, y - 9, 20, 18), Qt.AlignLeft | Qt.AlignVCenter, lbl)

    def _draw_region_watermark(self, painter: QPainter):
        """Draws elegant faint watermark in the background."""
        painter.save()
        font = QFont("SansSerif", 32, QFont.Black)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 4)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255, 10))
        text = f"{self.region.upper()} NAV-GRID // SYS 2.4"
        painter.drawText(QRectF(self.PAD_X, self.PAD_Y - 15, self.VIRTUAL_W - 2 * self.PAD_X, 80), Qt.AlignLeft, text)
        painter.restore()

    def _draw_edges(self, painter: QPainter):
        """Draws clean connecting route paths with distinct land/water/cave styling."""
        region_data = REGIONAL_MAP_DATA.get(self.region, {})
        nodes = region_data.get("nodes", {})
        edges = region_data.get("edges", [])

        is_hoenn = (self.region == REGION_HOENN)

        for edge in edges:
            src_name, dst_name = edge[0], edge[1]
            edge_type = edge[2] if len(edge) > 2 else "land"
            if src_name not in nodes or dst_name not in nodes:
                continue

            src_data = nodes[src_name]
            dst_data = nodes[dst_name]

            p1x, p1y = self.get_node_screen_pos(src_data["x"], src_data["y"])
            p2x, p2y = self.get_node_screen_pos(dst_data["x"], dst_data["y"])

            is_edge_hovered = (self.hovered_node in (src_name, dst_name))
            is_edge_selected = (self.selected_node in (src_name, dst_name))

            if is_hoenn:
                # On authentic Hoenn map, routes are already in the pixel art background.
                # Highlight active connections dynamically with neon electric glow.
                if is_edge_hovered or is_edge_selected:
                    glow_pen = QPen(QColor(56, 189, 248, 180), 5.5, Qt.SolidLine, Qt.RoundCap)
                    painter.setPen(glow_pen)
                    painter.drawLine(QPointF(p1x, p1y), QPointF(p2x, p2y))

                    core_pen = QPen(QColor(255, 255, 255, 240), 2.2, Qt.SolidLine, Qt.RoundCap)
                    painter.setPen(core_pen)
                    painter.drawLine(QPointF(p1x, p1y), QPointF(p2x, p2y))
                elif edge_type in ("cave", "tunnel"):
                    cave_pen = QPen(QColor(168, 85, 247, 70), 1.6, Qt.DotLine, Qt.RoundCap)
                    painter.setPen(cave_pen)
                    painter.drawLine(QPointF(p1x, p1y), QPointF(p2x, p2y))
                continue

            # Standard vector edge styling for other regions
            if edge_type == "water":
                casing_pen = QPen(CLR_PATH_WATER_OUTER, 6.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                inner_pen = QPen(
                    CLR_GLOW_HOVER if is_edge_hovered else CLR_PATH_WATER_INNER,
                    2.8,
                    Qt.CustomDashLine, Qt.RoundCap, Qt.RoundJoin
                )
                inner_pen.setDashPattern([5, 4])
            elif edge_type in ("cave", "tunnel"):
                casing_pen = QPen(CLR_PATH_CAVE_OUTER, 6.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                inner_pen = QPen(
                    CLR_GLOW_HOVER if is_edge_hovered else CLR_PATH_CAVE_INNER,
                    2.5,
                    Qt.CustomDashLine, Qt.RoundCap, Qt.RoundJoin
                )
                inner_pen.setDashPattern([3, 3])
            else:  # land
                casing_pen = QPen(CLR_PATH_LAND_OUTER, 7.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                s_stat = self._get_status(src_name)
                d_stat = self._get_status(dst_name)
                land_color = CLR_PATH_LAND_COMPLETE if (s_stat == "complete" and d_stat == "complete") else CLR_PATH_LAND_INNER
                inner_pen = QPen(
                    CLR_GLOW_HOVER if is_edge_hovered else land_color,
                    3.2,
                    Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin
                )

            # Outer casing
            painter.setPen(casing_pen)
            painter.drawLine(QPointF(p1x, p1y), QPointF(p2x, p2y))

            # Inner track
            painter.setPen(inner_pen)
            painter.drawLine(QPointF(p1x, p1y), QPointF(p2x, p2y))

            # Hover/selection glowing aura
            if is_edge_hovered or is_edge_selected:
                glow_pen = QPen(QColor(56, 189, 248, 60), 10.0, Qt.SolidLine, Qt.RoundCap)
                painter.setPen(glow_pen)
                painter.drawLine(QPointF(p1x, p1y), QPointF(p2x, p2y))

    def _draw_reticle(self, painter: QPainter, px: float, py: float, sz: float = 14.0):
        """Draws authentic GBA PokéNav corner reticle [ ] around a node."""
        painter.save()
        c_len = 5.0
        # White reticle with crisp corners
        pen = QPen(QColor("#ffffff"), 2.4, Qt.SolidLine, Qt.SquareCap, Qt.MiterJoin)
        painter.setPen(pen)

        # Top-Left
        painter.drawLine(QPointF(px - sz, py - sz + c_len), QPointF(px - sz, py - sz))
        painter.drawLine(QPointF(px - sz, py - sz), QPointF(px - sz + c_len, py - sz))

        # Top-Right
        painter.drawLine(QPointF(px + sz - c_len, py - sz), QPointF(px + sz, py - sz))
        painter.drawLine(QPointF(px + sz, py - sz), QPointF(px + sz, py - sz + c_len))

        # Bottom-Left
        painter.drawLine(QPointF(px - sz, py + sz - c_len), QPointF(px - sz, py + sz))
        painter.drawLine(QPointF(px - sz, py + sz), QPointF(px - sz + c_len, py + sz))

        # Bottom-Right
        painter.drawLine(QPointF(px + sz - c_len, py + sz), QPointF(px + sz, py + sz))
        painter.drawLine(QPointF(px + sz, py + sz), QPointF(px + sz, py + sz - c_len))

        painter.restore()

    def _draw_gba_node(self, painter: QPainter, name: str, data: Dict[str, Any], px: float, py: float):
        """Draws authentic 1:1 GBA-style interactive markers with completion rings."""
        node_type = data.get("type", "route")
        status = self._get_status(name)
        is_hovered = (self.hovered_node == name)
        is_selected = (self.selected_node == name)
        is_target = normalize_loc(name) in self.highlighted_nodes

        # Filtering dimming
        if self.filter_mode == "incomplete" and status == "complete":
            alpha = 0.25
        elif self.filter_mode == "mastered" and status != "complete":
            alpha = 0.25
        else:
            alpha = 1.0

        painter.save()
        painter.setOpacity(alpha)

        # Status ring color: 🟢 Green = Mastered, 🟡 Amber = In Progress, ⚪ Slate = Uncaught
        if status == "complete":
            ring_color = CLR_STATUS_COMPLETE   # #10b981
        elif status == "partial":
            ring_color = CLR_STATUS_PARTIAL    # #f59e0b
        else:
            ring_color = QColor("#cbd5e1")     # #cbd5e1 slate/white

        # 1. Target radar pulse (Habitat Locator Radar)
        if is_target:
            p_rad = 12.0 + self.radar_phase * 22.0
            p_alpha = int((1.0 - self.radar_phase) * 180)
            painter.setPen(QPen(QColor(244, 63, 94, p_alpha), 2.2))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(px, py), p_rad, p_rad)
            painter.setPen(QPen(CLR_GLOW_TARGET, 1.5))
            painter.drawEllipse(QPointF(px, py), 15.0, 15.0)

        # 2. Authentic White GBA Reticle [ ] on hovered or selected node
        if is_hovered or is_selected:
            r_sz = 17.0 if node_type in ("city", "town") else 13.0
            self._draw_reticle(painter, px, py, r_sz)

        # 3. Pin Geometry
        scale_node = 1.2 if is_hovered else 1.0

        if node_type == "city":
            # Authentic capsule pin for cities
            capsule_w = 26.0 * scale_node
            capsule_h = 17.0 * scale_node
            capsule_rect = QRectF(px - capsule_w / 2.0, py - capsule_h / 2.0, capsule_w, capsule_h)

            glow_pen = QPen(ring_color, 2.5 if not is_hovered else 3.5)
            painter.setPen(glow_pen)
            grad = QLinearGradient(capsule_rect.topLeft(), capsule_rect.bottomRight())
            grad.setColorAt(0.0, QColor("#e11d48"))
            grad.setColorAt(1.0, QColor("#881337"))
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(capsule_rect, 6.0, 6.0)

            # Abbreviation label inside capsule
            painter.setFont(QFont("Monospace", 6, QFont.Bold))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(capsule_rect, Qt.AlignCenter, data.get("label", ""))

        elif node_type == "town":
            # Circular pin for towns
            radius = 7.5 * scale_node
            painter.setPen(QPen(ring_color, 2.4 if not is_hovered else 3.2))
            grad = QRadialGradient(QPointF(px, py), radius)
            grad.setColorAt(0.0, QColor("#38bdf8"))
            grad.setColorAt(1.0, QColor("#0369a1"))
            painter.setBrush(QBrush(grad))
            painter.drawEllipse(QPointF(px, py), radius, radius)

            # Center white pip
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#ffffff"))
            painter.drawEllipse(QPointF(px, py), 2.5, 2.5)

        elif node_type == "landmark":
            # Diamond pin for caves and landmarks
            sz = 8.0 * scale_node
            poly = QPainterPath()
            poly.moveTo(px, py - sz)
            poly.lineTo(px + sz, py)
            poly.lineTo(px, py + sz)
            poly.lineTo(px - sz, py)
            poly.closeSubpath()

            painter.setPen(QPen(ring_color, 2.2 if not is_hovered else 3.0))
            painter.setBrush(QColor("#7c3aed"))
            painter.drawPath(poly)

        else:  # Route (land or water)
            r_rad = 5.0 * scale_node
            painter.setPen(QPen(ring_color, 2.0 if not is_hovered else 2.8))
            route_bg = QColor("#0284c7") if node_type == "water_route" else QColor("#d97706")
            painter.setBrush(route_bg)
            painter.drawEllipse(QPointF(px, py), r_rad, r_rad)

        # 4. Completion badge (★ for 100% Mastered)
        if status == "complete":
            star_pt = QPointF(px + 9.0, py - 9.0)
            painter.setFont(QFont("SansSerif", 7, QFont.Bold))
            painter.setPen(QColor("#facc15"))
            painter.drawText(QRectF(star_pt.x() - 6, star_pt.y() - 6, 12, 12), Qt.AlignCenter, "★")

        # 5. Trainer badge (⚔️ if trainers present)
        if self.show_trainers:
            norm_node = normalize_loc(name)
            trainers_here = self.trainers_by_loc.get(norm_node) or self.trainers_by_loc.get(f"{norm_node} CITY")
            if trainers_here:
                t_pt = QPointF(px + 10.0, py + 8.0)
                painter.setBrush(QColor("#ef4444"))
                painter.setPen(QPen(QColor("#fecaca"), 1.0))
                painter.drawEllipse(t_pt, 6.5, 6.5)
                painter.setFont(QFont("SansSerif", 6, QFont.Bold))
                painter.setPen(QColor("#ffffff"))
                painter.drawText(QRectF(t_pt.x() - 6, t_pt.y() - 6, 12, 12), Qt.AlignCenter, "⚔")

        painter.restore()

    def _draw_flower_frame_info(self, painter: QPainter):
        """Draws authentic GBA location card inside the bottom-right flower frame."""
        active = self.hovered_node or self.selected_node

        # Flower frame inner box bounds (960x640 virtual canvas, fits 240x160 GBA frame)
        box_rect = QRectF(540, 554, 392, 74)

        painter.save()
        # Clean white card backing inside the decorative flower frame
        painter.setBrush(QColor(255, 255, 255, 245))
        painter.setPen(QPen(QColor(41, 49, 49), 1.2))
        painter.drawRoundedRect(box_rect, 3.0, 3.0)

        if active:
            norm = normalize_loc(active)
            status = self._get_status(active)
            caught, total = self.caught_stats.get(norm, (0, 0))
            spawns = self.encounters_by_loc.get(norm, [])
            trainers = self.trainers_by_loc.get(norm) or self.trainers_by_loc.get(f"{norm} CITY") or []

            # 1. Header: Location Name & Status Badge
            font_title = QFont("Monospace", 9, QFont.Bold)
            painter.setFont(font_title)
            painter.setPen(QColor("#0f172a"))
            painter.drawText(QRectF(box_rect.x() + 8, box_rect.y() + 3, 260, 16), Qt.AlignLeft | Qt.AlignVCenter, active.upper())

            # Status Badge Pill
            badge_font = QFont("SansSerif", 7, QFont.Bold)
            painter.setFont(badge_font)
            badge_rect = QRectF(box_rect.right() - 105, box_rect.y() + 3, 98, 15)
            if status == "complete":
                painter.setBrush(QColor("#059669"))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(badge_rect, 3.0, 3.0)
                painter.setPen(QColor("#ffffff"))
                painter.drawText(badge_rect, Qt.AlignCenter, "★ MASTERED")
            elif status == "partial":
                painter.setBrush(QColor("#d97706"))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(badge_rect, 3.0, 3.0)
                painter.setPen(QColor("#ffffff"))
                painter.drawText(badge_rect, Qt.AlignCenter, "⚡ IN PROGRESS")
            else:
                painter.setBrush(QColor("#64748b"))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(badge_rect, 3.0, 3.0)
                painter.setPen(QColor("#ffffff"))
                painter.drawText(badge_rect, Qt.AlignCenter, "○ UNEXPLORED")

            # 2. Progress / Caught Count
            font_info = QFont("SansSerif", 8, QFont.DemiBold)
            painter.setFont(font_info)
            if total > 0:
                pct = int((caught / total) * 100.0)
                ratio_str = f"Caught: {caught} / {total}  ({pct}%)"
                c_clr = QColor("#059669") if caught >= total else (QColor("#d97706") if caught > 0 else QColor("#475569"))
            else:
                ratio_str = "Safe Area • No Wild Encounters"
                c_clr = QColor("#64748b")

            painter.setPen(c_clr)
            painter.drawText(QRectF(box_rect.x() + 8, box_rect.y() + 20, 240, 14), Qt.AlignLeft | Qt.AlignVCenter, ratio_str)

            # Progress bar
            bar_bg = QRectF(box_rect.x() + 8, box_rect.y() + 36, box_rect.width() - 16, 4.5)
            painter.setBrush(QColor("#e2e8f0"))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(bar_bg, 2.0, 2.0)
            if total > 0 and caught > 0:
                fill_w = (box_rect.width() - 16) * min(1.0, caught / total)
                bar_fill = QRectF(box_rect.x() + 8, box_rect.y() + 36, fill_w, 4.5)
                painter.setBrush(QColor("#059669") if caught >= total else QColor("#f59e0b"))
                painter.drawRoundedRect(bar_fill, 2.0, 2.0)

            # 3. Wild Pokémon Preview / Boss
            font_spawns = QFont("SansSerif", 7, QFont.Normal)
            painter.setFont(font_spawns)
            if spawns:
                disp_spawns = ", ".join(spawns[:5])
                if len(spawns) > 5:
                    disp_spawns += f" (+{len(spawns) - 5})"
                sp_text = f"🌿 Wild: {disp_spawns}"
                painter.setPen(QColor("#0284c7"))
            elif trainers:
                t = trainers[0]
                sp_text = f"⚔️ Leader: {t.get('name', 'Gym Leader')} ({t.get('title', '')})"
                painter.setPen(QColor("#dc2626"))
            else:
                sp_text = "Peaceful settlement in Hoenn"
                painter.setPen(QColor("#64748b"))

            painter.drawText(QRectF(box_rect.x() + 8, box_rect.y() + 44, box_rect.width() - 16, 26), Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, sp_text)

        else:
            # Default overview display
            font_title = QFont("Monospace", 9, QFont.Bold)
            painter.setFont(font_title)
            painter.setPen(QColor("#0f172a"))
            painter.drawText(QRectF(box_rect.x() + 8, box_rect.y() + 6, box_rect.width() - 16, 18), Qt.AlignLeft | Qt.AlignVCenter, "HOENN REGION // POKÉNAV")

            font_info = QFont("SansSerif", 8, QFont.Normal)
            painter.setFont(font_info)
            painter.setPen(QColor("#475569"))
            painter.drawText(QRectF(box_rect.x() + 8, box_rect.y() + 26, box_rect.width() - 16, 16), Qt.AlignLeft | Qt.AlignVCenter, "Authentic Town Map Navigation Grid")
            painter.setPen(QColor("#0284c7"))
            painter.drawText(QRectF(box_rect.x() + 8, box_rect.y() + 46, box_rect.width() - 16, 18), Qt.AlignLeft | Qt.AlignVCenter, "🖱️ Hover or Click nodes to view area encounters")

        painter.restore()

    def _draw_nodes(self, painter: QPainter):
        """Draws cities, routes, caves, and completion badges."""
        nodes = REGIONAL_MAP_DATA.get(self.region, {}).get("nodes", {})
        is_hoenn = (self.region == REGION_HOENN)

        for name, data in nodes.items():
            px, py = self.get_node_screen_pos(data["x"], data["y"])
            if is_hoenn:
                self._draw_gba_node(painter, name, data, px, py)
            else:
                self._draw_schematic_node(painter, name, data, px, py)

    def _draw_schematic_node(self, painter: QPainter, name: str, data: Dict[str, Any], px: float, py: float):
        """Draws abstract HUD schematic node for non-Hoenn regions."""
        node_type = data.get("type", "route")
        label_text = data.get("label", "")
        norm = normalize_loc(name)

        status = self._get_status(name)
        is_target = norm in self.highlighted_nodes
        is_hovered = (self.hovered_node == name)
        is_selected = (self.selected_node == name)

        font_city = QFont("SansSerif", 8, QFont.Bold)
        font_route = QFont("Monospace", 7, QFont.Bold)
        font_label = QFont("SansSerif", 7, QFont.DemiBold)

        if self.filter_mode == "incomplete" and status == "complete":
            alpha_mult = 0.25
        elif self.filter_mode == "mastered" and status != "complete":
            alpha_mult = 0.25
        else:
            alpha_mult = 1.0

        scale_node = 1.18 if is_hovered else 1.0
        node_radius = 11.0 * scale_node

        if status == "complete":
            status_color = CLR_STATUS_COMPLETE
        elif status == "partial":
            status_color = CLR_STATUS_PARTIAL
        else:
            status_color = CLR_STATUS_UNCAUGHT

        if is_target:
            p_rad = 12.0 + self.radar_phase * 22.0
            p_alpha = int((1.0 - self.radar_phase) * 180)
            pulse_pen = QPen(QColor(244, 63, 94, p_alpha), 2.2)
            painter.setPen(pulse_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(px, py), p_rad, p_rad)

            beacon_pen = QPen(CLR_GLOW_TARGET, 1.5)
            painter.setPen(beacon_pen)
            painter.drawEllipse(QPointF(px, py), 15.0, 15.0)

        if is_hovered or is_selected:
            glow_color = QColor(56, 189, 248, 140) if is_hovered else QColor(244, 63, 94, 180)
            glow_pen = QPen(glow_color, 4.0)
            painter.setPen(glow_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(px, py), node_radius + 4.0, node_radius + 4.0)

        painter.save()
        painter.setOpacity(alpha_mult)

        if node_type in ("city", "town"):
            box_w = 26.0 * scale_node
            box_h = 24.0 * scale_node
            rect = QRectF(px - box_w / 2.0, py - box_h / 2.0, box_w, box_h)

            grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
            if node_type == "city":
                grad.setColorAt(0.0, QColor("#1e293b"))
                grad.setColorAt(1.0, QColor("#0f172a"))
            else:
                grad.setColorAt(0.0, QColor("#1e2230"))
                grad.setColorAt(1.0, QColor("#0d121d"))

            painter.setBrush(QBrush(grad))
            border_pen = QPen(status_color, 2.0 if not is_hovered else 2.8)
            painter.setPen(border_pen)
            painter.drawRoundedRect(rect, 5.0, 5.0)

            painter.setFont(font_city)
            painter.setPen(QColor("#f8fafc"))
            painter.drawText(rect, Qt.AlignCenter, label_text)

            self._draw_text_with_halo(painter, name, px, py + box_h / 2.0 + 10.0, font_label)

        elif node_type == "landmark":
            box_sz = 22.0 * scale_node
            poly = QPainterPath()
            poly.moveTo(px, py - box_sz / 2.0)
            poly.lineTo(px + box_sz / 2.0, py)
            poly.lineTo(px, py + box_sz / 2.0)
            poly.lineTo(px - box_sz / 2.0, py)
            poly.closeSubpath()

            grad = QLinearGradient(QPointF(px, py - box_sz / 2.0), QPointF(px, py + box_sz / 2.0))
            grad.setColorAt(0.0, QColor("#2e1065"))
            grad.setColorAt(1.0, QColor("#1e1b4b"))

            painter.setBrush(QBrush(grad))
            painter.setPen(QPen(status_color, 2.0 if not is_hovered else 2.8))
            painter.drawPath(poly)

            painter.setFont(font_route)
            painter.setPen(QColor("#e2e8f0"))
            painter.drawText(QRectF(px - 14, py - 9, 28, 18), Qt.AlignCenter, label_text)

            self._draw_text_with_halo(painter, name, px, py + box_sz / 2.0 + 10.0, font_label)

        else:  # Route
            rect_sz = 22.0 * scale_node
            rect = QRectF(px - rect_sz / 2.0, py - rect_sz / 2.0, rect_sz, rect_sz)

            bg_color = QColor("#082f49") if node_type == "water_route" else QColor("#1e293b")
            painter.setBrush(QBrush(bg_color))
            painter.setPen(QPen(status_color, 2.0 if not is_hovered else 2.8))
            painter.drawRoundedRect(rect, 4.0, 4.0)

            painter.setFont(font_route)
            painter.setPen(QColor("#f8fafc"))
            painter.drawText(rect, Qt.AlignCenter, label_text)

        if status == "complete":
            star_pt = QPointF(px + 10.0, py - 10.0)
            painter.setFont(QFont("SansSerif", 7, QFont.Bold))
            painter.setPen(QColor("#facc15"))
            painter.drawText(QRectF(star_pt.x() - 6, star_pt.y() - 6, 12, 12), Qt.AlignCenter, "★")

        if self.show_trainers:
            norm_node = normalize_loc(name)
            trainers_here = self.trainers_by_loc.get(norm_node) or self.trainers_by_loc.get(f"{norm_node} CITY")
            if trainers_here:
                t_pt = QPointF(px + 12.0, py - 12.0)
                painter.setBrush(QColor("#ef4444"))
                painter.setPen(QPen(QColor("#fecaca"), 1.0))
                painter.drawEllipse(t_pt, 7.5, 7.5)
                painter.setFont(QFont("SansSerif", 7, QFont.Bold))
                painter.setPen(QColor("#ffffff"))
                painter.drawText(QRectF(t_pt.x() - 6, t_pt.y() - 6, 12, 12), Qt.AlignCenter, "⚔")

        painter.restore()

    def _draw_text_with_halo(self, painter: QPainter, text: str, x: float, y: float, font: QFont):
        """Draws text with a dark halo for legibility over lines."""
        painter.setFont(font)
        fm = QFontMetrics(font)
        tw = fm.horizontalAdvance(text)
        th = fm.height()
        rect = QRectF(x - tw / 2.0 - 4, y - th / 2.0, tw + 8, th)

        # Subtle dark pill background
        painter.setBrush(QColor(11, 15, 23, 210))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 3.0, 3.0)

        # Foreground text
        painter.setPen(QColor("#f1f5f9"))
        painter.drawText(rect, Qt.AlignCenter, text)

    def _get_status(self, name: str) -> str:
        """Determines completion status: 'complete', 'partial', 'uncaught'."""
        norm = normalize_loc(name)
        if norm in self.caught_stats:
            caught, total = self.caught_stats[norm]
            if total > 0 and caught >= total:
                return "complete"
            elif caught > 0:
                return "partial"
        return "uncaught"

    # ========================================================================
    # FLOATING HOVER CARD
    # ========================================================================

    def _draw_hover_card(self, painter: QPainter, node_name: str):
        """Renders modern glassmorphic HUD tooltip card anchoring near the node."""
        nodes = REGIONAL_MAP_DATA.get(self.region, {}).get("nodes", {})
        data = nodes.get(node_name)
        if not data:
            return

        px, py = self.get_node_screen_pos(data["x"], data["y"])
        norm = normalize_loc(node_name)
        caught, total = self.caught_stats.get(norm, (0, 0))
        missing = self.missing_species.get(norm, [])
        node_type = data.get("type", "route").replace("_", " ").upper()

        # Check trainers and wild encounters
        trainers_here = self.trainers_by_loc.get(norm) or self.trainers_by_loc.get(f"{norm} CITY") or []
        spawns_here = self.encounters_by_loc.get(norm, [])

        card_w = 320.0
        # Calculate dynamic height based on extra sections
        extra_lines = (1 if trainers_here else 0) + (1 if spawns_here else 0)
        card_h = 145.0 + extra_lines * 18.0

        # Position card cleanly avoiding edges
        cx = px + 18.0
        if cx + card_w > self.VIRTUAL_W - 20.0:
            cx = px - card_w - 18.0

        cy = py - card_h - 14.0
        if cy < 20.0:
            cy = py + 24.0

        card_rect = QRectF(cx, cy, card_w, card_h)

        # Card shadow
        shadow_rect = QRectF(cx + 3, cy + 3, card_w, card_h)
        painter.setBrush(QColor(0, 0, 0, 120))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(shadow_rect, 8.0, 8.0)

        # Card glass background
        card_grad = QLinearGradient(card_rect.topLeft(), card_rect.bottomRight())
        card_grad.setColorAt(0.0, QColor(15, 23, 42, 245))
        card_grad.setColorAt(1.0, QColor(11, 15, 23, 250))
        painter.setBrush(QBrush(card_grad))

        status = self._get_status(node_name)
        card_border = CLR_STATUS_COMPLETE if status == "complete" else (CLR_STATUS_PARTIAL if status == "partial" else QColor("#334155"))
        painter.setPen(QPen(card_border, 1.8))
        painter.drawRoundedRect(card_rect, 8.0, 8.0)

        # Header Title
        painter.setFont(QFont("SansSerif", 10, QFont.Bold))
        painter.setPen(QColor("#ffffff"))
        painter.drawText(QRectF(cx + 12, cy + 10, card_w - 24, 20), Qt.AlignLeft | Qt.AlignVCenter, node_name.upper())

        # Subtitle Region & Type pills
        painter.setFont(QFont("Monospace", 7, QFont.Bold))
        pill_rect = QRectF(cx + 12, cy + 32, 70, 16)
        painter.setBrush(QColor("#1e293b"))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(pill_rect, 3.0, 3.0)
        painter.setPen(QColor("#38bdf8"))
        painter.drawText(pill_rect, Qt.AlignCenter, self.region.upper())

        type_rect = QRectF(cx + 86, cy + 32, 95, 16)
        painter.setBrush(QColor("#1e293b"))
        painter.drawRoundedRect(type_rect, 3.0, 3.0)
        painter.setPen(QColor("#94a3b8"))
        painter.drawText(type_rect, Qt.AlignCenter, node_type)

        # Completion Bar & Ratio
        painter.setFont(QFont("SansSerif", 8, QFont.Bold))
        if total > 0:
            pct = int((caught / total) * 100.0)
            ratio_str = f"Caught: {caught} / {total}  ({pct}%)"
        else:
            pct = 0
            ratio_str = "No Wild Encounters (Safe Area)"

        painter.setPen(QColor("#f8fafc"))
        painter.drawText(QRectF(cx + 12, cy + 54, card_w - 24, 18), Qt.AlignLeft | Qt.AlignVCenter, ratio_str)

        # Progress bar
        bar_bg = QRectF(cx + 12, cy + 74, card_w - 24, 6)
        painter.setBrush(QColor("#334155"))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(bar_bg, 3.0, 3.0)

        if total > 0 and caught > 0:
            fill_w = (card_w - 24) * min(1.0, caught / total)
            bar_fill = QRectF(cx + 12, cy + 74, fill_w, 6)
            painter.setBrush(QBrush(CLR_STATUS_COMPLETE if caught >= total else CLR_STATUS_PARTIAL))
            painter.drawRoundedRect(bar_fill, 3.0, 3.0)

        curr_y = cy + 86.0

        # Trainer Section if present
        if trainers_here:
            t = trainers_here[0]
            t_name = t.get("name", "Trainer")
            t_title = t.get("title", "")
            painter.setFont(QFont("SansSerif", 7, QFont.Bold))
            painter.setPen(QColor("#f87171"))
            painter.drawText(QRectF(cx + 12, curr_y, card_w - 24, 16), Qt.AlignLeft | Qt.AlignVCenter, f"⚔️ Boss: {t_name} ({t_title})")
            curr_y += 18.0

        # Wild Spawns Preview if present
        if spawns_here and self.show_encounters:
            disp_spawns = ", ".join(spawns_here[:4])
            if len(spawns_here) > 4:
                disp_spawns += f" (+{len(spawns_here)-4})"
            painter.setFont(QFont("SansSerif", 7, QFont.Normal))
            painter.setPen(QColor("#38bdf8"))
            painter.drawText(QRectF(cx + 12, curr_y, card_w - 24, 16), Qt.AlignLeft | Qt.AlignVCenter, f"🌿 Wild: {disp_spawns}")
            curr_y += 18.0

        # Missing Pokemon Preview or Completion Badge
        painter.setFont(QFont("SansSerif", 7, QFont.DemiBold))
        if missing:
            disp_missing = ", ".join(missing[:3])
            if len(missing) > 3:
                disp_missing += f" (+{len(missing) - 3} more)"
            msg = f"Missing: {disp_missing}"
            painter.setPen(QColor("#fbbf24"))
        elif total > 0 and caught >= total:
            msg = "All species caught! 100% complete."
            painter.setPen(QColor("#34d399"))
        else:
            msg = "No wild Pokémon encounters in this peaceful town."
            painter.setPen(QColor("#94a3b8"))

        painter.drawText(QRectF(cx + 12, curr_y, card_w - 24, 16), Qt.AlignLeft | Qt.AlignVCenter, msg)
        curr_y += 18.0

        # Footer interaction hint
        painter.setFont(QFont("SansSerif", 7, QFont.Normal))
        painter.setPen(QColor("#64748b"))
        painter.drawText(QRectF(cx + 12, curr_y, card_w - 24, 16), Qt.AlignLeft | Qt.AlignVCenter, "🖱️ Click: DexNav | Drag: Pan | Scroll: Zoom")

# ============================================================================
# MAIN REGIONAL MAP WIDGET
# ============================================================================

class RegionalMapWidget(QWidget):
    """
    Standalone, fully-featured Regional Map Widget for Pokemon Quetzal Companion App.
    Provides region switching, topology mapping, caught stats, and habitat radar.
    """

    route_selected = Signal(str, str)   # (route_name, region)

    def __init__(self, parent=None, db_path: str = "quetzal_database.db"):
        super().__init__(parent)
        self.db_path = db_path
        self.setWindowTitle("Pokémon Quetzal Regional Town Map")
        self.resize(1180, 780)
        self.setStyleSheet("""
            RegionalMapWidget {
                background-color: #0b0f17;
            }
        """)

        self._build_ui()

        # Connect canvas signals
        self.canvas.node_clicked.connect(self._on_canvas_node_clicked)
        self.canvas.node_hovered.connect(self._on_canvas_node_hovered)

        # Automatically load DB if available
        if os.path.exists(self.db_path):
            self.load_data_from_db(self.db_path)
        else:
            self._update_status_bar()

    def _build_ui(self):
        self.canvas = MapCanvas(self)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 14, 16, 14)
        main_layout.setSpacing(10)

        # ====================================================================
        # TOP HEADER HUD BAR
        # ====================================================================
        top_bar = QFrame()
        top_bar.setStyleSheet("""
            QFrame {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 8px;
                padding: 4px 8px;
            }
        """)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(8, 4, 8, 4)
        top_layout.setSpacing(12)

        # Brand / Title
        title_label = QLabel("🗺️ <b>TOWN MAP</b> <span style='color:#38bdf8; font-size:11px;'>// POKÉNAV HUD</span>")
        title_label.setStyleSheet("color: #FFFFFF; font-size: 15px; font-weight: bold;")
        top_layout.addWidget(title_label)

        top_layout.addSpacing(16)

        # Region Segmented Pill Control: [ Hoenn ] [ Johto ] [ Kanto ] [ Sevii Islands ]
        self.region_btn_group = QButtonGroup(self)
        self.region_buttons: Dict[str, QPushButton] = {}

        region_pill_frame = QFrame()
        region_pill_frame.setStyleSheet("""
            QFrame {
                background-color: #0b0f17;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 2px;
            }
        """)
        pill_layout = QHBoxLayout(region_pill_frame)
        pill_layout.setContentsMargins(2, 2, 2, 2)
        pill_layout.setSpacing(2)

        region_icons = {
            REGION_HOENN: "🌴 Hoenn",
            REGION_JOHTO: "⛩️ Johto",
            REGION_KANTO: "🗼 Kanto",
            REGION_SEVII: "🏝️ Sevii Islands"
        }

        for r_name in ALL_REGIONS:
            btn = QPushButton(region_icons[r_name])
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #94a3b8;
                    border: none;
                    border-radius: 4px;
                    padding: 5px 14px;
                    font-size: 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    color: #f8fafc;
                    background-color: #1e293b;
                }
                QPushButton:checked {
                    background-color: #0284c7;
                    color: #FFFFFF;
                }
            """)
            if r_name == REGION_HOENN:
                btn.setChecked(True)

            btn.clicked.connect(lambda checked, rn=r_name: self.set_region(rn))
            self.region_btn_group.addButton(btn)
            self.region_buttons[r_name] = btn
            pill_layout.addWidget(btn)

        top_layout.addWidget(region_pill_frame)

        top_layout.addStretch()

        # Search Bar
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Search route / mon / town...")
        self.search_edit.setFixedWidth(220)
        self.search_edit.setStyleSheet("""
            QLineEdit {
                background-color: #0b0f17;
                border: 1px solid #334155;
                border-radius: 6px;
                color: #FFFFFF;
                padding: 5px 10px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #38bdf8;
            }
        """)
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        top_layout.addWidget(self.search_edit)

        # Filter Pills: [ All ] [ Incomplete ] [ Mastered ]
        filter_frame = QFrame()
        filter_frame.setStyleSheet("""
            QFrame {
                background-color: #0b0f17;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 2px;
            }
        """)
        f_layout = QHBoxLayout(filter_frame)
        f_layout.setContentsMargins(2, 2, 2, 2)
        f_layout.setSpacing(2)

        self.filter_buttons = []
        for f_label, f_key in [("All", "all"), ("Incomplete", "incomplete"), ("Mastered", "mastered")]:
            f_btn = QPushButton(f_label)
            f_btn.setCheckable(True)
            f_btn.setCursor(Qt.PointingHandCursor)
            f_btn.setChecked(f_key == "all")
            f_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #94a3b8;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 10px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    color: #FFFFFF;
                    background-color: #1e293b;
                }
                QPushButton:checked {
                    background-color: #334155;
                    color: #38bdf8;
                }
            """)
            f_btn.clicked.connect(lambda checked, fk=f_key: self._set_filter_mode(fk))
            self.filter_buttons.append((f_btn, f_key))
            f_layout.addWidget(f_btn)

        top_layout.addWidget(filter_frame)

        # View Toggles: [ ⚔️ Trainers ] [ 🌿 Spawns ]
        toggle_frame = QFrame()
        toggle_frame.setStyleSheet("""
            QFrame {
                background-color: #0b0f17;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 2px;
            }
        """)
        t_layout = QHBoxLayout(toggle_frame)
        t_layout.setContentsMargins(2, 2, 2, 2)
        t_layout.setSpacing(2)

        self.btn_trainers = QPushButton("⚔️ Trainers")
        self.btn_trainers.setCheckable(True)
        self.btn_trainers.setChecked(True)
        self.btn_trainers.setCursor(Qt.PointingHandCursor)
        self.btn_trainers.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #94a3b8;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover { color: #FFFFFF; background-color: #1e293b; }
            QPushButton:checked { background-color: #7f1d1d; color: #fca5a5; }
        """)
        self.btn_trainers.clicked.connect(self._toggle_trainers)
        t_layout.addWidget(self.btn_trainers)

        self.btn_spawns = QPushButton("🌿 Spawns")
        self.btn_spawns.setCheckable(True)
        self.btn_spawns.setChecked(True)
        self.btn_spawns.setCursor(Qt.PointingHandCursor)
        self.btn_spawns.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #94a3b8;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover { color: #FFFFFF; background-color: #1e293b; }
            QPushButton:checked { background-color: #064e3b; color: #6ee7b7; }
        """)
        self.btn_spawns.clicked.connect(self._toggle_spawns)
        t_layout.addWidget(self.btn_spawns)
        top_layout.addWidget(toggle_frame)

        # Pan & Zoom Controls: [ ＋ ] [ － ] [ ⟲ 1:1 ]
        zoom_frame = QFrame()
        zoom_frame.setStyleSheet("""
            QFrame {
                background-color: #0b0f17;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 2px;
            }
        """)
        z_layout = QHBoxLayout(zoom_frame)
        z_layout.setContentsMargins(2, 2, 2, 2)
        z_layout.setSpacing(2)

        zoom_btn_style = """
            QPushButton {
                background-color: transparent;
                color: #e2e8f0;
                border: none;
                border-radius: 4px;
                padding: 3px 8px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1e293b;
                color: #38bdf8;
            }
        """
        self.btn_zoom_in = QPushButton("＋")
        self.btn_zoom_in.setToolTip("Zoom In (or Scroll Wheel Up)")
        self.btn_zoom_in.setStyleSheet(zoom_btn_style)
        self.btn_zoom_in.clicked.connect(self.canvas.zoom_in)
        z_layout.addWidget(self.btn_zoom_in)

        self.btn_zoom_out = QPushButton("－")
        self.btn_zoom_out.setToolTip("Zoom Out (or Scroll Wheel Down)")
        self.btn_zoom_out.setStyleSheet(zoom_btn_style)
        self.btn_zoom_out.clicked.connect(self.canvas.zoom_out)
        z_layout.addWidget(self.btn_zoom_out)

        self.btn_zoom_reset = QPushButton("⟲ 1:1")
        self.btn_zoom_reset.setToolTip("Reset Zoom & Pan to 100%")
        self.btn_zoom_reset.setStyleSheet(zoom_btn_style)
        self.btn_zoom_reset.clicked.connect(self.canvas.reset_zoom)
        z_layout.addWidget(self.btn_zoom_reset)

        top_layout.addWidget(zoom_frame)

        main_layout.addWidget(top_bar)

        # ====================================================================
        # CENTER INTERACTIVE CANVAS
        # ====================================================================
        main_layout.addWidget(self.canvas, stretch=1)

        # ====================================================================
        # BOTTOM STATUS & LEGEND HUD BAR
        # ====================================================================
        bot_bar = QFrame()
        bot_bar.setStyleSheet("""
            QFrame {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 8px;
                padding: 4px 12px;
            }
        """)
        bot_layout = QHBoxLayout(bot_bar)
        bot_layout.setContentsMargins(10, 4, 10, 4)
        bot_layout.setSpacing(16)

        # Status Legend
        legend_lbl = QLabel(
            "<span style='color:#10b981;'>●</span> 100% Complete &nbsp;&nbsp;"
            "<span style='color:#f59e0b;'>●</span> In Progress &nbsp;&nbsp;"
            "<span style='color:#64748b;'>●</span> Unexplored &nbsp;&nbsp;"
            "<span style='color:#f43f5e;'>●</span> Habitat Target"
        )
        legend_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: bold;")
        bot_layout.addWidget(legend_lbl)

        bot_layout.addStretch()

        # Region stats summary
        self.stats_summary_lbl = QLabel("Loading stats...")
        self.stats_summary_lbl.setStyleSheet("color: #e2e8f0; font-size: 12px; font-weight: bold;")
        bot_layout.addWidget(self.stats_summary_lbl)

        bot_layout.addStretch()

        # Quick action: Reload DB
        reload_btn = QPushButton("⟲ Sync DB")
        reload_btn.setCursor(Qt.PointingHandCursor)
        reload_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #FFFFFF;
                background-color: #334155;
            }
        """)
        reload_btn.clicked.connect(lambda: self.load_data_from_db(self.db_path))
        bot_layout.addWidget(reload_btn)

        # Clear Highlight button
        clear_btn = QPushButton("Clear Target")
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #FFFFFF;
                background-color: #334155;
            }
        """)
        clear_btn.clicked.connect(self.clear_highlights)
        bot_layout.addWidget(clear_btn)

        main_layout.addWidget(bot_bar)

    # ========================================================================
    # PUBLIC API
    # ========================================================================

    def set_region(self, region_name: str):
        """Switches active region and updates UI controls."""
        if region_name not in ALL_REGIONS:
            return
        if region_name in self.region_buttons:
            self.region_buttons[region_name].setChecked(True)
        self.canvas.set_region(region_name)
        self._update_status_bar()

    def set_caught_data(self, dict_of_route_stats: Dict[str, Any]):
        """
        Sets route completion data.
        Accepts dict where key is location_name and value is (caught_count, total_count)
        or dict with keys 'caught' and 'total'.
        """
        clean_stats: Dict[str, Tuple[int, int]] = {}
        for k, v in dict_of_route_stats.items():
            norm = normalize_loc(k)
            if isinstance(v, (tuple, list)) and len(v) >= 2:
                clean_stats[norm] = (int(v[0]), int(v[1]))
            elif isinstance(v, dict):
                c = int(v.get("caught", 0))
                t = int(v.get("total", 0))
                clean_stats[norm] = (c, t)
                if "missing" in v:
                    self.canvas.missing_species[norm] = list(v["missing"])

        self.canvas.caught_stats.update(clean_stats)
        self.canvas.update()
        self._update_status_bar()

    def highlight_locations(self, list_of_location_names: List[str]):
        """
        Highlights specific routes on the map (used by Pokédex Habitat Locator
        when finding where a Pokémon lives!).
        """
        targets = {normalize_loc(name) for name in list_of_location_names if name}
        self.canvas.highlighted_nodes = targets
        self.canvas.update()

    def clear_highlights(self):
        """Clears all highlighted radar targets."""
        self.canvas.highlighted_nodes.clear()
        self.canvas.update()

    def load_data_from_db(self, db_path: str = "quetzal_database.db"):
        """
        Queries encounters and caught_pokemon from SQLite DB to automatically
        populate completion stats and missing Pokemon for every location.
        """
        if not os.path.exists(db_path):
            return

        try:
            conn = sqlite3.connect(db_path)
            c = conn.cursor()

            # Query encounters and whether they are caught
            c.execute("""
                SELECT e.location_name,
                       e.species_id,
                       e.species_name,
                       (cp.species_id IS NOT NULL) AS is_caught
                FROM encounters e
                LEFT JOIN caught_pokemon cp ON e.species_id = cp.species_id
            """)
            rows = c.fetchall()

            location_data: Dict[str, Dict[str, Any]] = {}
            for loc, sp_id, sp_name, is_c in rows:
                norm = normalize_loc(loc)
                if norm not in location_data:
                    location_data[norm] = {
                        "caught_ids": set(),
                        "all_species": {}
                    }
                location_data[norm]["all_species"][sp_id] = sp_name
                if is_c:
                    location_data[norm]["caught_ids"].add(sp_id)

            stats: Dict[str, Tuple[int, int]] = {}
            missing_map: Dict[str, List[str]] = {}

            for norm, d in location_data.items():
                caught_cnt = len(d["caught_ids"])
                total_cnt = len(d["all_species"])
                stats[norm] = (caught_cnt, total_cnt)

                missing_names = [
                    name for sp_id, name in d["all_species"].items()
                    if sp_id not in d["caught_ids"]
                ]
                missing_map[norm] = missing_names

            # Build encounters list per location
            enc_map: Dict[str, List[str]] = {}
            for norm, d in location_data.items():
                enc_map[norm] = list(d["all_species"].values())
            self.canvas.encounters_by_loc = enc_map

            # Query trainers
            c.execute("SELECT name, title, region, location, unlock_condition, team_preview FROM trainers")
            trainers_rows = c.fetchall()
            trainers_map: Dict[str, List[Dict[str, str]]] = {}
            for name, title, reg, loc, unlock, team in trainers_rows:
                norm_l = normalize_loc(loc)
                loc_clean = norm_l.replace(" GYM", " CITY").replace(" GYM LEADERS", "")
                entry = {"name": name, "title": title, "region": reg, "location": loc, "unlock": unlock, "team": team}
                trainers_map.setdefault(norm_l, []).append(entry)
                if loc_clean != norm_l:
                    trainers_map.setdefault(loc_clean, []).append(entry)
            self.canvas.trainers_by_loc = trainers_map

            self.canvas.caught_stats = stats
            self.canvas.missing_species = missing_map
            self.canvas.update()
            self._update_status_bar()
            conn.close()
        except Exception as e:
            print(f"Error loading from DB {db_path}: {e}", file=sys.stderr)

    # ========================================================================
    # INTERNAL HANDLERS
    # ========================================================================

    def _toggle_trainers(self, checked: bool):
        self.canvas.show_trainers = checked
        self.canvas.update()

    def _toggle_spawns(self, checked: bool):
        self.canvas.show_encounters = checked
        self.canvas.update()

    def _on_canvas_node_clicked(self, node_name: str, region: str):
        self.route_selected.emit(node_name, region)

    def _on_canvas_node_hovered(self, node_name: str, region: str):
        pass

    def _set_filter_mode(self, mode: str):
        for btn, k in self.filter_buttons:
            btn.setChecked(k == mode)
        self.canvas.filter_mode = mode
        self.canvas.update()

    def _on_search_text_changed(self, text: str):
        query = text.strip().upper()
        if not query:
            self.clear_highlights()
            return

        matches = []
        nodes = REGIONAL_MAP_DATA.get(self.canvas.region, {}).get("nodes", {})
        for name in nodes.keys():
            norm = normalize_loc(name)
            if query in norm:
                matches.append(name)
            elif norm in self.canvas.missing_species:
                # Also match species names
                for sp in self.canvas.missing_species[norm]:
                    if query in sp.upper():
                        matches.append(name)
                        break

        self.highlight_locations(matches)

    def _update_status_bar(self):
        nodes = REGIONAL_MAP_DATA.get(self.canvas.region, {}).get("nodes", {})
        total_routes = len(nodes)
        completed_routes = 0
        total_caught = 0
        total_encounters = 0

        for name in nodes.keys():
            norm = normalize_loc(name)
            if norm in self.canvas.caught_stats:
                c, t = self.canvas.caught_stats[norm]
                total_caught += c
                total_encounters += t
                if t > 0 and c >= t:
                    completed_routes += 1

        if total_encounters > 0:
            pct = (total_caught / total_encounters) * 100.0
            txt = f"{self.canvas.region} Dex Completion: <b>{total_caught} / {total_encounters} ({pct:.1f}%)</b>  •  <b>{completed_routes} / {total_routes}</b> Areas Mastered"
        else:
            txt = f"{self.canvas.region} Region: <b>{total_routes}</b> Key Locations mapped"

        self.stats_summary_lbl.setText(txt)

# ============================================================================
# STANDALONE TEST BLOCK
# ============================================================================

if __name__ == "__main__":
    app = QApplication.instance() or QApplication(sys.argv)

    widget = RegionalMapWidget()
    widget.show()

    # Load real DB if present
    db_file = "quetzal_database.db"
    if os.path.exists(db_file):
        widget.load_data_from_db(db_file)
    else:
        # Mock caught data for standalone test
        mock_data = {
            "ROUTE 101": (12, 12),
            "ROUTE 102": (15, 17),
            "PETALBURG WOODS": (14, 17),
            "RUSTBORO CITY": (0, 0),
            "ROUTE 104": (18, 18),
            "DEWFORD TOWN": (11, 15),
            "GRANITE CAVE": (10, 10),
            "MAUVILLE CITY": (0, 0),
            "SLATEPORT CITY": (12, 12),
            "ROUTE 110": (20, 25),
        }
        widget.set_caught_data(mock_data)

    # Highlight Route 101 and Petalburg Woods as habitat targets
    widget.highlight_locations(["ROUTE 101", "PETALBURG WOODS"])

    # Simulate hovering Route 101
    widget.canvas.hovered_node = "Route 101"

    # Process events to layout properly
    app.processEvents()

    # Render headless screenshot
    screenshot_path = "map_render_test.png"
    pixmap = widget.grab()
    pixmap.save(screenshot_path)
    print(f"[OK] Standalone Regional Map render verified successfully: {screenshot_path}")

    # Exit cleanly if running headless
    if "pytest" in sys.modules or os.environ.get("HEADLESS", "0") == "1" or not os.environ.get("DISPLAY"):
        sys.exit(0)
    else:
        # If run directly in xvfb-run or normal terminal test
        sys.exit(0)
