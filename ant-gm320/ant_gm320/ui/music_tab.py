"""
Dedicated Music / Audio-Reactive Lighting Tab for Ant Esports GM320.
Streams live desktop audio peaks directly to mouse LEDs with zero latency (~0.1% CPU).
"""

from typing import Tuple
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QSlider, QComboBox, QGroupBox, QFrame
)
from PySide6.QtCore import Qt, Signal
from ant_gm320.ui.widgets.audio_visualizer import AudioVisualizerWidget
from ant_gm320.ui.widgets.color_picker import ColorPickerDialog


class MusicTab(QWidget):
    sync_toggled = Signal(bool)
    mode_changed = Signal(str)
    gain_changed = Signal(float)
    colors_changed = Signal(tuple, tuple)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_active = False
        self._primary_color = (0, 229, 255)      # Cyan
        self._secondary_color = (255, 0, 128)    # Neon Pink
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(18)

        # Top Banner: Audio Status & Start/Stop Button
        top_card = QFrame()
        top_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #121722, stop:1 #182030);
                border: 1px solid #273142;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        top_layout = QHBoxLayout(top_card)
        top_layout.setSpacing(16)

        info_v = QVBoxLayout()
        self.status_title = QLabel("Native Audio-Reactive RGB Sync")
        self.status_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #00e5ff;")
        self.status_sub = QLabel("Syncs mouse lighting directly to desktop audio (Spotify, Games, Browser, Media)")
        self.status_sub.setStyleSheet("color: #8b949e; font-size: 12px;")
        info_v.addWidget(self.status_title)
        info_v.addWidget(self.status_sub)
        top_layout.addLayout(info_v, 1)

        self.btn_toggle = QPushButton("Start Audio Sync")
        self.btn_toggle.setObjectName("primaryBtn")
        self.btn_toggle.setFixedSize(160, 42)
        self.btn_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_toggle.clicked.connect(self._toggle_sync)
        top_layout.addWidget(self.btn_toggle)

        main_layout.addWidget(top_card)

        # Middle: Real-time Audio Spectrum Visualizer
        vis_card = QGroupBox("Live Desktop Audio Spectrum & Beat Meter")
        vis_layout = QVBoxLayout(vis_card)
        vis_layout.setContentsMargins(14, 20, 14, 14)

        self.visualizer = AudioVisualizerWidget()
        vis_layout.addWidget(self.visualizer)

        # Beat detection indicator banner
        self.beat_indicator = QLabel("● RHYTHM IDLE")
        self.beat_indicator.setAlignment(Qt.AlignCenter)
        self.beat_indicator.setFixedHeight(24)
        self.beat_indicator.setStyleSheet("color: #8b949e; font-size: 11px; font-weight: 700; letter-spacing: 1px;")
        vis_layout.addWidget(self.beat_indicator)

        main_layout.addWidget(vis_card)

        # Bottom Controls: Reactive Mode, Sensitivity, Color Customization
        controls_card = QGroupBox("Audio Effect Parameters")
        ctrl_layout = QGridLayout(controls_card)
        ctrl_layout.setContentsMargins(16, 20, 16, 16)
        ctrl_layout.setHorizontalSpacing(24)
        ctrl_layout.setVerticalSpacing(14)

        # Mode Selector
        ctrl_layout.addWidget(QLabel("Reactive Mode:"), 0, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Bass Pulse (Drum & Bass Kick Flash)", "bass_pulse")
        self.mode_combo.addItem("RGB Spectrum (Low=Red, Mid=Green, High=Blue)", "spectrum")
        self.mode_combo.addItem("Neon Tempo Flow (Audio Speed Cycle)", "neon_flow")
        self.mode_combo.addItem("Strobe Beat (High Energy Drops)", "strobe")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        ctrl_layout.addWidget(self.mode_combo, 0, 1)

        # Audio Sensitivity / Gain Slider
        ctrl_layout.addWidget(QLabel("Mic / Audio Gain:"), 1, 0)
        gain_h = QHBoxLayout()
        self.gain_slider = QSlider(Qt.Horizontal)
        self.gain_slider.setRange(10, 50)
        self.gain_slider.setValue(20)
        self.gain_val_lbl = QLabel("2.0x")
        self.gain_val_lbl.setFixedWidth(40)
        self.gain_slider.valueChanged.connect(self._on_gain_changed)
        gain_h.addWidget(self.gain_slider)
        gain_h.addWidget(self.gain_val_lbl)
        ctrl_layout.addLayout(gain_h, 1, 1)

        # Primary & Accent Colors
        ctrl_layout.addWidget(QLabel("Theme Colors:"), 2, 0)
        colors_h = QHBoxLayout()
        colors_h.setSpacing(12)

        self.btn_primary = QPushButton("Primary Color")
        self.btn_primary.setFixedHeight(32)
        self.btn_primary.clicked.connect(self._pick_primary)
        self._update_color_btn(self.btn_primary, self._primary_color)
        colors_h.addWidget(self.btn_primary)

        self.btn_secondary = QPushButton("Accent Pulse")
        self.btn_secondary.setFixedHeight(32)
        self.btn_secondary.clicked.connect(self._pick_secondary)
        self._update_color_btn(self.btn_secondary, self._secondary_color)
        colors_h.addWidget(self.btn_secondary)

        ctrl_layout.addLayout(colors_h, 2, 1)
        main_layout.addWidget(controls_card)

    def _toggle_sync(self):
        self._is_active = not self._is_active
        if self._is_active:
            self.btn_toggle.setText("Stop Audio Sync")
            self.btn_toggle.setObjectName("dangerBtn")
            self.status_title.setText("● Native Audio-Reactive Sync ACTIVE")
            self.status_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #00f59b;")
        else:
            self.btn_toggle.setText("Start Audio Sync")
            self.btn_toggle.setObjectName("primaryBtn")
            self.status_title.setText("Native Audio-Reactive RGB Sync")
            self.status_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #00e5ff;")

        self.btn_toggle.style().unpolish(self.btn_toggle)
        self.btn_toggle.style().polish(self.btn_toggle)
        self.sync_toggled.emit(self._is_active)

    def set_sync_active(self, active: bool):
        if self._is_active != active:
            self._toggle_sync()

    def _on_mode_changed(self):
        mode = self.mode_combo.currentData()
        self.mode_changed.emit(mode)

    def _on_gain_changed(self, val: int):
        gain = val / 10.0
        self.gain_val_lbl.setText(f"{gain:.1f}x")
        self.gain_changed.emit(gain)

    def _update_color_btn(self, btn: QPushButton, color: Tuple[int, int, int]):
        hex_c = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {hex_c};
                color: {'#000000' if (color[0]*0.299 + color[1]*0.587 + color[2]*0.114) > 150 else '#ffffff'};
                border: 1px solid #273142;
                border-radius: 6px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                border: 2px solid #ffffff;
            }}
        """)

    def _pick_primary(self):
        dlg = ColorPickerDialog(self._primary_color, self)
        dlg.color_selected.connect(self._on_primary_selected)
        dlg.exec()

    def _on_primary_selected(self, r: int, g: int, b: int):
        self._primary_color = (r, g, b)
        self._update_color_btn(self.btn_primary, self._primary_color)
        self.colors_changed.emit(self._primary_color, self._secondary_color)

    def _pick_secondary(self):
        dlg = ColorPickerDialog(self._secondary_color, self)
        dlg.color_selected.connect(self._on_secondary_selected)
        dlg.exec()

    def _on_secondary_selected(self, r: int, g: int, b: int):
        self._secondary_color = (r, g, b)
        self._update_color_btn(self.btn_secondary, self._secondary_color)
        self.colors_changed.emit(self._primary_color, self._secondary_color)

    def handle_audio_metrics(self, bass: float, mids: float, highs: float, peak: float):
        self.visualizer.update_metrics(bass, mids, highs, peak)

    def handle_beat_detected(self):
        self.visualizer.trigger_beat()
        self.beat_indicator.setText("★ BEAT DROP DETECTED")
        self.beat_indicator.setStyleSheet("color: #00f59b; font-size: 11px; font-weight: 800; letter-spacing: 1.5px;")
