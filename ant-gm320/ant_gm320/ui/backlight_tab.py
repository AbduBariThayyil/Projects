"""
Backlight / RGB Lighting Configuration Tab for Ant Esports GM320.
Features:
- Integrated Single-Card UI: Lighting Mode, Sliders, Direction/Symmetry, Custom Palette, and Button Response.
- Dynamic Button Response Trigger Grid with Presets (All Ripple, Clicks Flash, Side Burst, Rainbow Strobe).
- One-Click Themes: Cyberpunk, Firestorm, Vaporwave, Oceanic, Matrix, Esports Gold, Full Rainbow.
- Custom 7-Color Palette with interactive swatches and slot enable toggles.
- All Instant Microelectronics OEM modes supported.
- Clean Lighting Zone Visualizer without button callout badges.
"""

from typing import Dict, Any, List
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QLabel,
    QComboBox, QSlider, QCheckBox, QRadioButton, QButtonGroup,
    QGroupBox, QPushButton, QFrame, QScrollArea
)
from PySide6.QtCore import Qt, Signal
from ant_gm320.ui.widgets.mouse_preview import MousePreviewWidget
from ant_gm320.ui.widgets.color_picker import ColorPickerDialog
from ant_gm320.core.protocol import LED_MODES, LED_MODE_NAMES, REACTION_TYPES

THEME_PRESETS = [
    ("Cyberpunk", [[0, 229, 255], [255, 0, 128]], [True, True, False, False, False, False, False]),
    ("Firestorm", [[255, 0, 50], [255, 100, 0], [255, 220, 0]], [True, True, True, False, False, False, False]),
    ("Vaporwave", [[121, 40, 202], [255, 0, 128], [0, 229, 255]], [True, True, True, False, False, False, False]),
    ("Oceanic", [[0, 68, 255], [0, 229, 255], [0, 255, 170]], [True, True, True, False, False, False, False]),
    ("Matrix", [[0, 255, 100], [0, 150, 50]], [True, True, False, False, False, False, False]),
    ("Esports Gold", [[255, 215, 0], [255, 255, 255]], [True, True, False, False, False, False, False]),
    ("Full Rainbow", [
        [0, 240, 255], [255, 255, 0], [255, 0, 0],
        [255, 0, 180], [0, 0, 255], [0, 150, 50], [0, 255, 0]
    ], [True, True, True, True, True, True, True]),
]

BUTTON_NAMES = [
    "K1 Left",
    "K2 Right",
    "K3 Middle",
    "K4 DPI",
    "K5 LED",
    "K6 Rapid",
    "K7 Fwd",
    "K8 Back",
]


class BacklightTab(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._palette_colors = [
            [0, 229, 255], [255, 255, 0], [255, 0, 0],
            [255, 0, 180], [0, 0, 255], [0, 150, 50], [0, 255, 0]
        ]
        self._palette_enables = [True, True, True, True, True, True, True]
        self._color_buttons: List[QPushButton] = []
        self._color_checkboxes: List[QCheckBox] = []

        self._btn_react_enables: List[QCheckBox] = []
        self._btn_react_types: List[QComboBox] = []

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(20)

        # Left Column: Pure Lighting Zone Visualizer (Badges Disabled)
        left_col = QVBoxLayout()
        left_col.setSpacing(10)

        preview_card = QGroupBox("Lighting Zone Visualizer")
        prev_layout = QVBoxLayout(preview_card)
        prev_layout.setContentsMargins(10, 14, 10, 14)
        self.mouse_preview = MousePreviewWidget()
        self.mouse_preview.set_show_badges(False)  # Clean aesthetic lighting aura
        prev_layout.addWidget(self.mouse_preview)

        hint_lbl = QLabel("Live RGB Aura & Zone Preview")
        hint_lbl.setAlignment(Qt.AlignCenter)
        hint_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        prev_layout.addWidget(hint_lbl)

        left_col.addWidget(preview_card)
        main_layout.addLayout(left_col, 4)

        # Right Column: Unified Backlight & Color Combination Menu in ScrollArea
        right_col = QVBoxLayout()
        right_col.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: #0d1117;
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #273142;
                border-radius: 3px;
                min-height: 24px;
            }
            QScrollBar::handle:vertical:hover {
                background: #00e5ff;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 0, 4, 0)
        scroll_layout.setSpacing(12)

        # Single Unified Lighting Card
        unified_card = QGroupBox("Backlight & RGB Lighting Settings")
        card_layout = QVBoxLayout(unified_card)
        card_layout.setContentsMargins(16, 18, 16, 16)
        card_layout.setSpacing(12)

        # 1. Backlight Mode Selector
        mode_h = QHBoxLayout()
        mode_lbl = QLabel("Backlight Mode:")
        mode_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #f0f6fc; border: none; background: transparent;")
        mode_h.addWidget(mode_lbl)

        self.mode_combo = QComboBox()
        self.mode_combo.setMinimumWidth(220)
        for code, name in LED_MODE_NAMES.items():
            self.mode_combo.addItem(name, code)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_h.addWidget(self.mode_combo, 0, Qt.AlignRight)
        card_layout.addLayout(mode_h)

        # 2. Sliders (Speed & Brightness)
        sliders_box = QFrame()
        sliders_box.setObjectName("slidersBox")
        sliders_box.setStyleSheet("""
            QFrame#slidersBox {
                background-color: #0f1520;
                border: 1px solid #1c2738;
                border-radius: 6px;
            }
            QFrame#slidersBox QLabel {
                border: none;
                background: transparent;
            }
        """)
        sliders_layout = QVBoxLayout(sliders_box)
        sliders_layout.setContentsMargins(12, 10, 12, 10)
        sliders_layout.setSpacing(8)

        # Speed
        speed_h = QHBoxLayout()
        sp_lbl = QLabel("Effect Speed:")
        sp_lbl.setStyleSheet("color: #c9d1d9; font-weight: 600; font-size: 12px;")
        speed_h.addWidget(sp_lbl)
        self.speed_val = QLabel("5 / 10")
        self.speed_val.setStyleSheet("color: #00e5ff; font-weight: 700; font-size: 12px;")
        speed_h.addWidget(self.speed_val, 0, Qt.AlignRight)
        sliders_layout.addLayout(speed_h)

        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(1, 10)
        self.speed_slider.setValue(5)
        self.speed_slider.valueChanged.connect(lambda v: (self.speed_val.setText(f"{v} / 10"), self.changed.emit()))
        sliders_layout.addWidget(self.speed_slider)

        # Brightness
        bright_h = QHBoxLayout()
        br_lbl = QLabel("LED Brightness:")
        br_lbl.setStyleSheet("color: #c9d1d9; font-weight: 600; font-size: 12px;")
        bright_h.addWidget(br_lbl)
        self.bright_val = QLabel("4 / 5")
        self.bright_val.setStyleSheet("color: #00e5ff; font-weight: 700; font-size: 12px;")
        bright_h.addWidget(self.bright_val, 0, Qt.AlignRight)
        sliders_layout.addLayout(bright_h)

        self.bright_slider = QSlider(Qt.Horizontal)
        self.bright_slider.setRange(1, 5)
        self.bright_slider.setValue(4)
        self.bright_slider.valueChanged.connect(lambda v: (self.bright_val.setText(f"{v} / 5"), self.changed.emit()))
        sliders_layout.addWidget(self.bright_slider)

        # Symmetry & Direction
        flags_row = QHBoxLayout()
        self.chk_symmetry = QCheckBox("Bilateral Symmetry")
        self.chk_symmetry.setToolTip("Mirror RGB lighting strips across left and right sides")
        self.chk_symmetry.setStyleSheet("color: #c9d1d9; font-size: 11px; border: none; background: transparent;")
        self.chk_symmetry.toggled.connect(lambda _: self.changed.emit())
        flags_row.addWidget(self.chk_symmetry)

        flags_row.addSpacing(14)
        dir_lbl = QLabel("Direction:")
        dir_lbl.setStyleSheet("color: #8b949e; font-size: 11px; font-weight: 600; border: none; background: transparent;")
        flags_row.addWidget(dir_lbl)
        self.dir_group = QButtonGroup(self)
        self.radio_cw = QRadioButton("CW")
        self.radio_ccw = QRadioButton("CCW")
        self.radio_cw.setChecked(True)
        self.radio_cw.setStyleSheet("color: #c9d1d9; font-size: 11px; border: none; background: transparent;")
        self.radio_ccw.setStyleSheet("color: #c9d1d9; font-size: 11px; border: none; background: transparent;")
        self.dir_group.addButton(self.radio_cw, 0)
        self.dir_group.addButton(self.radio_ccw, 1)
        self.dir_group.idClicked.connect(lambda _: self.changed.emit())
        flags_row.addWidget(self.radio_cw)
        flags_row.addWidget(self.radio_ccw)
        flags_row.addStretch()
        sliders_layout.addLayout(flags_row)

        card_layout.addWidget(sliders_box)

        # 3. Integrated Custom Lighting & Color Combinations
        colors_header = QLabel("Custom Colors & Dynamic Palette:")
        colors_header.setStyleSheet("color: #00e5ff; font-size: 11px; font-weight: 700; text-transform: uppercase; margin-top: 2px; border: none; background: transparent;")
        card_layout.addWidget(colors_header)

        colors_frame = QFrame()
        colors_frame.setObjectName("colorsFrame")
        colors_frame.setStyleSheet("""
            QFrame#colorsFrame {
                background-color: #0f1520;
                border: 1px solid #1c2738;
                border-radius: 6px;
            }
            QFrame#colorsFrame QLabel {
                border: none;
                background: transparent;
            }
        """)
        colors_v = QVBoxLayout(colors_frame)
        colors_v.setContentsMargins(12, 10, 12, 10)
        colors_v.setSpacing(8)

        # One-Click Theme Pills (Wrapping in clean flow grid)
        themes_grid = QGridLayout()
        themes_grid.setHorizontalSpacing(6)
        themes_grid.setVerticalSpacing(4)
        for i, (t_name, t_colors, t_ens) in enumerate(THEME_PRESETS):
            btn = QPushButton(t_name)
            btn.setFixedHeight(24)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #161f2e;
                    border: 1px solid #273142;
                    border-radius: 12px;
                    color: #c9d1d9;
                    font-size: 10px;
                    font-weight: 600;
                    padding: 0 8px;
                }
                QPushButton:hover {
                    border-color: #00e5ff;
                    color: #00e5ff;
                    background-color: #1c2738;
                }
            """)
            btn.clicked.connect(lambda _, c=t_colors, e=t_ens: self._apply_theme(c, e))
            themes_grid.addWidget(btn, i // 4, i % 4)
        colors_v.addLayout(themes_grid)

        # 7 Palette Swatches with Checkboxes
        palette_row = QHBoxLayout()
        palette_row.setSpacing(10)
        palette_row.setAlignment(Qt.AlignCenter)

        for i in range(7):
            slot_v = QVBoxLayout()
            slot_v.setSpacing(4)
            slot_v.setAlignment(Qt.AlignCenter)

            btn = QPushButton()
            btn.setFixedSize(30, 30)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(f"Palette Slot {i + 1}: Click to edit RGB color")
            btn.clicked.connect(lambda _, idx=i: self._edit_palette_color(idx))
            self._color_buttons.append(btn)
            slot_v.addWidget(btn)

            chk = QCheckBox()
            chk.setChecked(True)
            chk.setToolTip(f"Enable Color {i + 1} in effect cycle")
            chk.setStyleSheet("border: none; background: transparent;")
            chk.toggled.connect(lambda checked, idx=i: self._on_color_toggled(idx, checked))
            self._color_checkboxes.append(chk)
            slot_v.addWidget(chk, 0, Qt.AlignCenter)

            palette_row.addLayout(slot_v)

        colors_v.addLayout(palette_row)
        self._update_palette_buttons()
        card_layout.addWidget(colors_frame)

        # 4. Button Response Trigger Configuration (Visible when Button Response is active)
        self.react_container = QFrame()
        self.react_container.setObjectName("reactContainer")
        self.react_container.setStyleSheet("""
            QFrame#reactContainer {
                background-color: #0f1520;
                border: 1px solid #1c2738;
                border-radius: 6px;
            }
            QFrame#reactContainer QLabel {
                border: none;
                background: transparent;
            }
        """)
        react_v = QVBoxLayout(self.react_container)
        react_v.setContentsMargins(12, 10, 12, 10)
        react_v.setSpacing(8)

        react_header = QHBoxLayout()
        react_title = QLabel("Button Response Triggers & Reaction Effects:")
        react_title.setStyleSheet("color: #00e5ff; font-size: 11px; font-weight: 700; text-transform: uppercase;")
        react_header.addWidget(react_title)
        react_v.addLayout(react_header)

        # Reaction Presets Row
        presets_row = QHBoxLayout()
        presets_row.setSpacing(5)
        react_presets = [
            ("All Ripple", lambda: self._apply_reaction_preset(all_type=0)),
            ("Clicks Flash", lambda: self._apply_reaction_preset(types_dict={0: 2, 1: 2, 2: 2})),
            ("Side Burst", lambda: self._apply_reaction_preset(types_dict={5: 1, 6: 1, 7: 1})),
            ("Rainbow Strobe", lambda: self._apply_reaction_preset(all_type=3)),
            ("All Active", lambda: self._apply_reaction_preset(all_en=True)),
        ]
        for p_name, p_func in react_presets:
            p_btn = QPushButton(p_name)
            p_btn.setFixedHeight(22)
            p_btn.setCursor(Qt.PointingHandCursor)
            p_btn.setStyleSheet("""
                QPushButton {
                    background-color: #161f2e;
                    border: 1px solid #273142;
                    border-radius: 4px;
                    color: #c9d1d9;
                    font-size: 10px;
                    font-weight: 600;
                    padding: 0 6px;
                }
                QPushButton:hover {
                    border-color: #00e5ff;
                    color: #00e5ff;
                }
            """)
            p_btn.clicked.connect(p_func)
            presets_row.addWidget(p_btn)
        react_v.addLayout(presets_row)

        # 8-Button Reaction Trigger Grid (2 columns x 4 rows)
        btn_grid = QGridLayout()
        btn_grid.setHorizontalSpacing(10)
        btn_grid.setVerticalSpacing(6)

        for i in range(8):
            row = i % 4
            col_base = (i // 4) * 2

            chk = QCheckBox(BUTTON_NAMES[i])
            chk.setChecked(True)
            chk.setStyleSheet("font-size: 11px; color: #f0f6fc; border: none; background: transparent;")
            chk.toggled.connect(lambda _: self.changed.emit())
            self._btn_react_enables.append(chk)
            btn_grid.addWidget(chk, row, col_base)

            combo = QComboBox()
            combo.setFixedWidth(105)
            combo.setStyleSheet("font-size: 11px; padding: 2px 4px;")
            for r_code, r_name in REACTION_TYPES.items():
                combo.addItem(r_name, r_code)
            combo.currentIndexChanged.connect(lambda _: self.changed.emit())
            self._btn_react_types.append(combo)
            btn_grid.addWidget(combo, row, col_base + 1)

        react_v.addLayout(btn_grid)
        card_layout.addWidget(self.react_container)

        scroll_layout.addWidget(unified_card)
        scroll.setWidget(scroll_widget)
        right_col.addWidget(scroll)

        main_layout.addLayout(right_col, 6)

        # Trigger initial mode visibility
        self._on_mode_changed()

    def _apply_theme(self, colors: List[List[int]], enables: List[bool]):
        for i in range(min(len(colors), 7)):
            self._palette_colors[i] = list(colors[i])
        for i in range(min(len(enables), 7)):
            self._palette_enables[i] = enables[i]
            self._color_checkboxes[i].setChecked(enables[i])

        self._update_palette_buttons()
        # Set preview glow to first active color
        for i, en in enumerate(self._palette_enables):
            if en:
                c = self._palette_colors[i]
                self.mouse_preview.set_glow_color(c[0], c[1], c[2])
                break
        self.changed.emit()

    def _apply_reaction_preset(self, all_type: int = None, types_dict: Dict[int, int] = None, all_en: bool = None):
        if all_en is not None:
            for chk in self._btn_react_enables:
                chk.setChecked(all_en)
        if all_type is not None:
            for combo in self._btn_react_types:
                idx = combo.findData(all_type)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
        if types_dict is not None:
            for b_idx, r_code in types_dict.items():
                if 0 <= b_idx < len(self._btn_react_types):
                    combo = self._btn_react_types[b_idx]
                    idx = combo.findData(r_code)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
        self.changed.emit()

    def _on_color_toggled(self, idx: int, checked: bool):
        if not checked and sum(self._palette_enables) <= 1:
            self._color_checkboxes[idx].setChecked(True)
            return

        self._palette_enables[idx] = checked
        self._update_palette_buttons()
        self.changed.emit()

    def _update_palette_buttons(self):
        for i, btn in enumerate(self._color_buttons):
            c = self._palette_colors[i]
            hex_c = f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}"
            enabled = self._palette_enables[i]
            opacity = "1.0" if enabled else "0.3"
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {hex_c};
                    border: {'2px solid #00e5ff' if enabled else '1px solid #273142'};
                    border-radius: 15px;
                    opacity: {opacity};
                }}
                QPushButton:hover {{
                    border: 2px solid #ffffff;
                }}
            """)

    def _edit_palette_color(self, idx: int):
        c = self._palette_colors[idx]
        dlg = ColorPickerDialog((c[0], c[1], c[2]), self)
        dlg.color_selected.connect(lambda r, g, b: self._set_palette_color(idx, r, g, b))
        dlg.exec()

    def _set_palette_color(self, idx: int, r: int, g: int, b: int):
        self._palette_colors[idx] = [r, g, b]
        self._update_palette_buttons()
        self.mouse_preview.set_glow_color(r, g, b)
        self.changed.emit()

    def _on_mode_changed(self):
        code = self.mode_combo.currentData()
        # Show button response controls when Button Response (13 or 3) is active
        is_button_response = (code in [13, 3])
        self.react_container.setVisible(is_button_response)

        # Update preview glow based on mode
        if code in [7, 8, 16]:  # Neon, Ambilight, Cycle Color
            self.mouse_preview.set_glow_color(0, 229, 255)
        elif code in [2, 3, 15]:  # Cycle Breath, Static, Single Breath
            c = self._palette_colors[0]
            self.mouse_preview.set_glow_color(c[0], c[1], c[2])
        elif code == 14:  # Off
            self.mouse_preview.set_glow_color(20, 20, 25)
        elif is_button_response:
            c = self._palette_colors[0]
            self.mouse_preview.set_glow_color(c[0], c[1], c[2])
        self.changed.emit()

    def load_config(self, config: Dict[str, Any]):
        led = config.get("lighting", {})
        mode = led.get("mode", 8)
        idx = self.mode_combo.findData(mode)
        if idx >= 0:
            self.mode_combo.setCurrentIndex(idx)
        else:
            self.mode_combo.setCurrentIndex(0)

        speed = led.get("speed", 5)
        self.speed_slider.setValue(speed)
        self.speed_val.setText(f"{speed} / 10")

        bright = led.get("brightness", 4)
        self.bright_slider.setValue(bright)
        self.bright_val.setText(f"{bright} / 5")

        self.chk_symmetry.setChecked(led.get("symmetry", False))
        if led.get("direction", "cw") == "ccw":
            self.radio_ccw.setChecked(True)
        else:
            self.radio_cw.setChecked(True)

        colors = led.get("colors")
        if colors and len(colors) >= 7:
            self._palette_colors = [list(c) for c in colors[:7]]

        enables = led.get("color_enables")
        if enables and len(enables) >= 7:
            self._palette_enables = list(enables[:7])
            for i in range(7):
                self._color_checkboxes[i].setChecked(self._palette_enables[i])

        # Load Button Response settings
        btn_react = led.get("button_response", {})
        r_ens = btn_react.get("enables", [True] * 8)
        r_types = btn_react.get("types", [0, 0, 0, 0, 0, 0, 0, 3])
        for i in range(8):
            if i < len(r_ens) and i < len(self._btn_react_enables):
                self._btn_react_enables[i].setChecked(bool(r_ens[i]))
            if i < len(r_types) and i < len(self._btn_react_types):
                combo = self._btn_react_types[i]
                c_idx = combo.findData(r_types[i])
                if c_idx >= 0:
                    combo.setCurrentIndex(c_idx)

        self._update_palette_buttons()
        self._on_mode_changed()

    def save_config(self, config: Dict[str, Any]):
        config["lighting"] = {
            "mode": self.mode_combo.currentData(),
            "speed": self.speed_slider.value(),
            "brightness": self.bright_slider.value(),
            "symmetry": self.chk_symmetry.isChecked(),
            "direction": "ccw" if self.radio_ccw.isChecked() else "cw",
            "colors": [list(c) for c in self._palette_colors],
            "color_enables": list(self._palette_enables),
            "button_response": {
                "enables": [chk.isChecked() for chk in self._btn_react_enables],
                "types": [combo.currentData() for combo in self._btn_react_types],
            }
        }
