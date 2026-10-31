"""
Modern Color Picker dialog for Ant Esports GM320.
Includes esports gaming swatches and high-precision RGB sliders.
"""

from typing import Tuple, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QGridLayout, QWidget, QLineEdit
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

ESPORTS_SWATCHES = [
    ("#ffff00", "Yellow"),
    ("#00e5ff", "Cyan"),
    ("#ff007f", "Magenta"),
    ("#00ff66", "Lime"),
    ("#ff3333", "Red"),
    ("#0066ff", "Blue"),
    ("#9933ff", "Purple"),
    ("#ff8800", "Orange"),
    ("#ffffff", "White"),
    ("#00ffea", "Aquamarine"),
    ("#ff0033", "Crimson"),
    ("#10141e", "Off / Dark"),
]


class ColorPickerDialog(QDialog):
    color_selected = Signal(int, int, int)

    def __init__(self, initial_color: Tuple[int, int, int] = (0, 229, 255), parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose Color")
        self.setFixedSize(360, 420)
        self.setModal(True)

        self._r, self._g, self._b = initial_color

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Title
        title = QLabel("Select RGB Color")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #00e5ff;")
        layout.addWidget(title)

        # Color Preview Banner
        self.preview_box = QLabel()
        self.preview_box.setFixedHeight(50)
        self.preview_box.setStyleSheet(f"border-radius: 8px; border: 2px solid #273142;")
        layout.addWidget(self.preview_box)

        # Presets Grid
        presets_label = QLabel("Esports Presets")
        presets_label.setStyleSheet("color: #8b949e; font-size: 11px; text-transform: uppercase; font-weight: 600;")
        layout.addWidget(presets_label)

        grid = QGridLayout()
        grid.setSpacing(8)
        for i, (hex_code, name) in enumerate(ESPORTS_SWATCHES):
            btn = QPushButton()
            btn.setFixedSize(40, 30)
            btn.setToolTip(name)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {hex_code};
                    border: 1px solid #273142;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    border: 2px solid #ffffff;
                }}
            """)
            btn.clicked.connect(lambda _, h=hex_code: self._set_from_hex(h))
            grid.addWidget(btn, i // 6, i % 6)
        layout.addLayout(grid)

        # Custom Sliders
        sliders_label = QLabel("Fine Tune (RGB)")
        sliders_label.setStyleSheet("color: #8b949e; font-size: 11px; text-transform: uppercase; font-weight: 600;")
        layout.addWidget(sliders_label)

        sliders_layout = QVBoxLayout()
        sliders_layout.setSpacing(10)

        # Red Slider
        self.r_slider = self._create_slider("Red", self._r, "#ff3366")
        self.r_slider.valueChanged.connect(self._on_slider_changed)
        sliders_layout.addWidget(self._wrap_slider("R", self.r_slider))

        # Green Slider
        self.g_slider = self._create_slider("Green", self._g, "#00f59b")
        self.g_slider.valueChanged.connect(self._on_slider_changed)
        sliders_layout.addWidget(self._wrap_slider("G", self.g_slider))

        # Blue Slider
        self.b_slider = self._create_slider("Blue", self._b, "#00e5ff")
        self.b_slider.valueChanged.connect(self._on_slider_changed)
        sliders_layout.addWidget(self._wrap_slider("B", self.b_slider))

        layout.addLayout(sliders_layout)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        confirm_btn = QPushButton("Select")
        confirm_btn.setObjectName("primaryBtn")
        confirm_btn.clicked.connect(self._on_confirm)
        btn_layout.addWidget(confirm_btn)

        layout.addLayout(btn_layout)
        self._update_preview()

    def _create_slider(self, name: str, val: int, color_accent: str) -> QSlider:
        s = QSlider(Qt.Horizontal)
        s.setRange(0, 255)
        s.setValue(val)
        return s

    def _wrap_slider(self, label_text: str, slider: QSlider) -> QWidget:
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(label_text)
        lbl.setFixedWidth(20)
        lbl.setStyleSheet("font-weight: 700; color: #8b949e;")
        val_lbl = QLabel(str(slider.value()))
        val_lbl.setFixedWidth(30)
        slider.valueChanged.connect(lambda v: val_lbl.setText(str(v)))
        l.addWidget(lbl)
        l.addWidget(slider)
        l.addWidget(val_lbl)
        return w

    def _set_from_hex(self, hex_code: str):
        c = QColor(hex_code)
        self._r, self._g, self._b = c.red(), c.green(), c.blue()
        self.r_slider.setValue(self._r)
        self.g_slider.setValue(self._g)
        self.b_slider.setValue(self._b)
        self._update_preview()

    def _on_slider_changed(self):
        self._r = self.r_slider.value()
        self._g = self.g_slider.value()
        self._b = self.b_slider.value()
        self._update_preview()

    def _update_preview(self):
        hex_code = f"#{self._r:02x}{self._g:02x}{self._b:02x}"
        self.preview_box.setStyleSheet(f"""
            background-color: {hex_code};
            border-radius: 8px;
            border: 2px solid #273142;
        """)
        self.preview_box.setText(f"   {hex_code.upper()}  (RGB: {self._r}, {self._g}, {self._b})")
        self.preview_box.setStyleSheet(f"""
            background-color: {hex_code};
            border-radius: 8px;
            border: 2px solid #273142;
            color: {'#000000' if (self._r*0.299 + self._g*0.587 + self._b*0.114) > 150 else '#ffffff'};
            font-weight: 700;
        """)

    def _on_confirm(self):
        self.color_selected.emit(self._r, self._g, self._b)
        self.accept()

    def get_color(self) -> Tuple[int, int, int]:
        return (self._r, self._g, self._b)
