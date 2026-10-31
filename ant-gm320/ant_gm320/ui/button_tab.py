"""
Button Assignment Tab for Ant Esports GM320.
Features interactive mouse diagram with glowing callouts and custom action dropdowns for buttons 1-8.
"""

from typing import Dict, Any
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QLabel,
    QComboBox, QGroupBox, QPushButton, QSlider, QSpinBox
)
from PySide6.QtCore import Qt, Signal
from ant_gm320.ui.widgets.mouse_preview import MousePreviewWidget
from ant_gm320.core.protocol import BUTTON_FUNCTIONS, BUTTON_NAMES

BUTTON_LABELS = [
    (1, "1. Left Click"),
    (2, "2. Right Click"),
    (3, "3. Middle Click"),
    (4, "4. DPI Switch"),
    (5, "5. LED Loop"),
    (6, "6. Rapid Fire"),
    (7, "7. Forward"),
    (8, "8. Backward"),
]


class ButtonTab(QWidget):
    changed = Signal()
    open_music_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._combos: Dict[int, QComboBox] = {}
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(28)

        # Left Column: Mouse Diagram & Music-Lighting shortcut button
        left_col = QVBoxLayout()
        left_col.setSpacing(16)

        diagram_card = QGroupBox("Interactive Mouse Map")
        diag_layout = QVBoxLayout(diagram_card)
        self.mouse_preview = MousePreviewWidget()
        self.mouse_preview.button_clicked.connect(self._on_mouse_diagram_clicked)
        diag_layout.addWidget(self.mouse_preview)
        left_col.addWidget(diagram_card)

        # Music Lighting Quick Button on bottom-left (as shown in official OEM screenshot)
        music_btn = QPushButton("♫  Music Lighting (Audio Sync)")
        music_btn.setFixedHeight(40)
        music_btn.setCursor(Qt.PointingHandCursor)
        music_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #161b24, stop:1 #1e2636);
                border: 1px solid #00e5ff;
                border-radius: 6px;
                color: #00e5ff;
                font-weight: 700;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.15);
                border: 2px solid #00e5ff;
            }
        """)
        music_btn.clicked.connect(self.open_music_requested.emit)
        left_col.addWidget(music_btn)

        main_layout.addLayout(left_col, 4)

        # Right Column: Button Assignment Selectors
        right_col = QVBoxLayout()
        right_col.setSpacing(16)

        actions_card = QGroupBox("8-Button Key Configuration")
        actions_layout = QGridLayout(actions_card)
        actions_layout.setVerticalSpacing(12)
        actions_layout.setHorizontalSpacing(16)
        actions_layout.setContentsMargins(16, 22, 16, 16)

        for row, (btn_num, label_text) in enumerate(BUTTON_LABELS):
            lbl = QLabel(label_text)
            lbl.setStyleSheet("font-weight: 600; color: #f0f6fc;")
            combo = QComboBox()
            combo.setMinimumWidth(180)

            # Populate functions
            for code, name in BUTTON_NAMES.items():
                combo.addItem(name, code)

            combo.currentIndexChanged.connect(self._on_combo_changed)
            self._combos[btn_num] = combo

            actions_layout.addWidget(lbl, row, 0)
            actions_layout.addWidget(combo, row, 1)

        right_col.addWidget(actions_card)

        # Rapid Fire Parameter Settings
        rapid_card = QGroupBox("Rapid Fire Tuning (Button 6)")
        rapid_layout = QHBoxLayout(rapid_card)
        rapid_layout.setContentsMargins(16, 18, 16, 14)

        delay_lbl = QLabel("Burst Delay:")
        self.fire_slider = QSlider(Qt.Horizontal)
        self.fire_slider.setRange(10, 200)
        self.fire_slider.setValue(50)
        self.fire_val_lbl = QLabel("50 ms")
        self.fire_val_lbl.setFixedWidth(50)
        self.fire_slider.valueChanged.connect(lambda v: (self.fire_val_lbl.setText(f"{v} ms"), self.changed.emit()))

        rapid_layout.addWidget(delay_lbl)
        rapid_layout.addWidget(self.fire_slider)
        rapid_layout.addWidget(self.fire_val_lbl)

        right_col.addWidget(rapid_card)
        main_layout.addLayout(right_col, 5)

    def _on_mouse_diagram_clicked(self, btn_num: int):
        if btn_num in self._combos:
            self._combos[btn_num].setFocus()

    def _on_combo_changed(self):
        # Update mouse preview selected button
        for num, combo in self._combos.items():
            if combo.hasFocus():
                self.mouse_preview.set_selected_button(num)
                break
        self.changed.emit()

    def load_config(self, config: Dict[str, Any]):
        buttons = config.get("buttons", {})
        mapping = {
            1: buttons.get("button1", 0x21),
            2: buttons.get("button2", 0x22),
            3: buttons.get("button3", 0x23),
            4: buttons.get("button4", 0x26),
            5: buttons.get("button5", 0x29),
            6: buttons.get("button6", 0x35),
            7: buttons.get("button7", 0x24),
            8: buttons.get("button8", 0x25),
        }
        for btn_num, code in mapping.items():
            combo = self._combos.get(btn_num)
            if combo:
                idx = combo.findData(code)
                if idx >= 0:
                    combo.setCurrentIndex(idx)

        perf = config.get("performance", {})
        fire_time = perf.get("fire_delay", 50)
        self.fire_slider.setValue(fire_time)
        self.fire_val_lbl.setText(f"{fire_time} ms")

    def save_config(self, config: Dict[str, Any]):
        buttons = {
            "button1": self._combos[1].currentData(),
            "button2": self._combos[2].currentData(),
            "button3": self._combos[3].currentData(),
            "button4": self._combos[4].currentData(),
            "button5": self._combos[5].currentData(),
            "button6": self._combos[6].currentData(),
            "button7": self._combos[7].currentData(),
            "button8": self._combos[8].currentData(),
        }
        config["buttons"] = buttons
        if "performance" not in config:
            config["performance"] = {}
        config["performance"]["fire_delay"] = self.fire_slider.value()
