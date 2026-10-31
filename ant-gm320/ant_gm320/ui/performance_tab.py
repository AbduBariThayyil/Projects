"""
Performance Configuration Tab for Ant Esports GM320.
Features:
- Fully dynamic, customizable DPI builder (arbitrary number of stages, toggle stages,
  fine-tune sliders 200 - 12800 DPI, custom RGB stage color chips, active stage selector).
- Polling Rate selector (125 Hz, 250 Hz, 500 Hz, 1000 Hz).
- Mouse Sensitivity (1-11) and Wheel Scroll Speed (1-11).
- Double-Click speed slider with live interactive test pad.
"""

from typing import Dict, Any, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QPushButton, QGroupBox, QSpinBox, QCheckBox, QRadioButton,
    QButtonGroup, QScrollArea, QFrame
)
from PySide6.QtCore import Qt, Signal
from ant_gm320.ui.widgets.color_picker import ColorPickerDialog
from ant_gm320.ui.widgets.double_click_test import DoubleClickTestWidget

POLLING_RATES = [125, 250, 500, 1000]


class StageRowWidget(QFrame):
    stage_changed = Signal()
    remove_requested = Signal(object)
    activated_requested = Signal(int)

    def __init__(self, stage_idx: int, stage_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.stage_idx = stage_idx
        self.stage_data = stage_data

        self.setStyleSheet("""
            StageRowWidget {
                background-color: #12161f;
                border: 1px solid #273142;
                border-radius: 6px;
            }
            StageRowWidget:hover {
                border-color: #3a86ff;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(14)

        # Radio button to set as currently active stage
        self.radio_active = QRadioButton()
        self.radio_active.setToolTip("Set as active DPI stage")
        self.radio_active.toggled.connect(self._on_radio_toggled)
        layout.addWidget(self.radio_active)

        # Enable / Disable toggle
        self.chk_enabled = QCheckBox(f"Stage {stage_idx + 1}")
        self.chk_enabled.setChecked(stage_data.get("enabled", True))
        self.chk_enabled.setStyleSheet("font-weight: 700; color: #f0f6fc;")
        self.chk_enabled.toggled.connect(self._on_enabled_toggled)
        layout.addWidget(self.chk_enabled)

        # Color chip button
        self.btn_color = QPushButton()
        self.btn_color.setFixedSize(26, 26)
        self.btn_color.setCursor(Qt.PointingHandCursor)
        self.btn_color.setToolTip("Click to change stage color")
        self.btn_color.clicked.connect(self._open_color_picker)
        self._update_color_chip()
        layout.addWidget(self.btn_color)

        # DPI Slider
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(200, 12800)
        self.slider.setSingleStep(100)
        self.slider.setPageStep(500)
        self.slider.setValue(stage_data.get("dpi", 1200))
        self.slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.slider, 1)

        # DPI Spinbox
        self.spin = QSpinBox()
        self.spin.setRange(200, 12800)
        self.spin.setSingleStep(100)
        self.spin.setValue(stage_data.get("dpi", 1200))
        self.spin.setSuffix(" DPI")
        self.spin.setFixedWidth(110)
        self.spin.valueChanged.connect(self._on_spin_changed)
        layout.addWidget(self.spin)

        # Remove button
        self.btn_remove = QPushButton("✕")
        self.btn_remove.setFixedSize(24, 24)
        self.btn_remove.setToolTip("Remove this stage")
        self.btn_remove.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #8b949e;
                border: none;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton:hover {
                color: #ff3366;
            }
        """)
        self.btn_remove.clicked.connect(lambda: self.remove_requested.emit(self))
        layout.addWidget(self.btn_remove)

    def _update_color_chip(self):
        c = self.stage_data.get("color", [0, 229, 255])
        hex_c = f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}"
        self.btn_color.setStyleSheet(f"""
            QPushButton {{
                background-color: {hex_c};
                border: 2px solid #ffffff;
                border-radius: 13px;
            }}
            QPushButton:hover {{
                border: 2px solid #00e5ff;
            }}
        """)

    def _open_color_picker(self):
        c = self.stage_data.get("color", [0, 229, 255])
        dlg = ColorPickerDialog((c[0], c[1], c[2]), self)
        dlg.color_selected.connect(self._on_color_selected)
        dlg.exec()

    def _on_color_selected(self, r: int, g: int, b: int):
        self.stage_data["color"] = [r, g, b]
        self._update_color_chip()
        self.stage_changed.emit()

    def _on_slider_changed(self, val: int):
        # Snap to nearest 100
        val = int(round(val / 100.0) * 100)
        if self.spin.value() != val:
            self.spin.setValue(val)
        self.stage_data["dpi"] = val
        self.stage_changed.emit()

    def _on_spin_changed(self, val: int):
        if self.slider.value() != val:
            self.slider.setValue(val)
        self.stage_data["dpi"] = val
        self.stage_changed.emit()

    def _on_enabled_toggled(self, checked: bool):
        self.stage_data["enabled"] = checked
        self.slider.setEnabled(checked)
        self.spin.setEnabled(checked)
        self.btn_color.setEnabled(checked)
        self.stage_changed.emit()

    def _on_radio_toggled(self, checked: bool):
        if checked:
            self.activated_requested.emit(self.stage_idx)

    def get_data(self) -> Dict[str, Any]:
        return {
            "dpi": self.spin.value(),
            "enabled": self.chk_enabled.isChecked(),
            "color": self.stage_data.get("color", [0, 229, 255]),
        }


class PerformanceTab(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stage_widgets: List[StageRowWidget] = []
        self._active_stage_idx = 0
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(28)

        # Left Column: Sensitivity, Scroll Speed, Double Click Speed
        left_col = QVBoxLayout()
        left_col.setSpacing(16)

        # Pointer Precision & Sensitivity
        sens_card = QGroupBox("Pointer Precision & Scroll")
        sens_layout = QVBoxLayout(sens_card)
        sens_layout.setSpacing(14)
        sens_layout.setContentsMargins(16, 22, 16, 16)

        # Mouse Sensitivity (1-11)
        sens_h = QHBoxLayout()
        sens_h.addWidget(QLabel("Mouse Sensitivity:"))
        self.sens_val = QLabel("6 / 11")
        self.sens_val.setStyleSheet("color: #00e5ff; font-weight: 700;")
        sens_h.addWidget(self.sens_val, 0, Qt.AlignRight)
        sens_layout.addLayout(sens_h)

        self.sens_slider = QSlider(Qt.Horizontal)
        self.sens_slider.setRange(1, 11)
        self.sens_slider.setValue(6)
        self.sens_slider.valueChanged.connect(lambda v: (self.sens_val.setText(f"{v} / 11"), self.changed.emit()))
        sens_layout.addWidget(self.sens_slider)

        # Scroll Speed (1-11)
        scroll_h = QHBoxLayout()
        scroll_h.addWidget(QLabel("Scroll Speed (Wheel):"))
        self.scroll_val = QLabel("4 / 11")
        self.scroll_val.setStyleSheet("color: #00e5ff; font-weight: 700;")
        scroll_h.addWidget(self.scroll_val, 0, Qt.AlignRight)
        sens_layout.addLayout(scroll_h)

        self.scroll_slider = QSlider(Qt.Horizontal)
        self.scroll_slider.setRange(1, 11)
        self.scroll_slider.setValue(4)
        self.scroll_slider.valueChanged.connect(lambda v: (self.scroll_val.setText(f"{v} / 11"), self.changed.emit()))
        sens_layout.addWidget(self.scroll_slider)

        # Double-Click Speed (ms)
        dc_h = QHBoxLayout()
        dc_h.addWidget(QLabel("Double-Click Speed:"))
        self.dc_val = QLabel("140 ms")
        self.dc_val.setStyleSheet("color: #00e5ff; font-weight: 700;")
        dc_h.addWidget(self.dc_val, 0, Qt.AlignRight)
        sens_layout.addLayout(dc_h)

        self.dc_slider = QSlider(Qt.Horizontal)
        self.dc_slider.setRange(50, 400)
        self.dc_slider.setValue(140)
        self.dc_slider.valueChanged.connect(lambda v: (self.dc_val.setText(f"{v} ms"), self.changed.emit()))
        sens_layout.addWidget(self.dc_slider)

        # Interactive Double Click Pad
        self.dc_test_widget = DoubleClickTestWidget()
        sens_layout.addWidget(self.dc_test_widget)

        left_col.addWidget(sens_card)

        # Polling Rate Card
        poll_card = QGroupBox("Polling Rate (USB Report)")
        poll_layout = QHBoxLayout(poll_card)
        poll_layout.setContentsMargins(16, 20, 16, 16)
        poll_layout.setSpacing(10)

        self.poll_group = QButtonGroup(self)
        for rate in POLLING_RATES:
            btn = QPushButton(f"{rate} Hz")
            btn.setCheckable(True)
            btn.setFixedHeight(36)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #12161f;
                    border: 1px solid #273142;
                    border-radius: 6px;
                    color: #8b949e;
                    font-weight: 700;
                }
                QPushButton:checked {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00b4d8, stop:1 #00e5ff);
                    color: #050a12;
                    border: none;
                }
            """)
            self.poll_group.addButton(btn, rate)
            poll_layout.addWidget(btn)

        self.poll_group.idClicked.connect(lambda _: self.changed.emit())
        # Default 500 Hz
        btn_500 = self.poll_group.button(500)
        if btn_500:
            btn_500.setChecked(True)

        left_col.addWidget(poll_card)
        main_layout.addLayout(left_col, 4)

        # Right Column: Dynamic DPI Stage Builder
        right_col = QVBoxLayout()
        right_col.setSpacing(12)

        dpi_card = QGroupBox("Custom DPI Stages (Dynamic Builder)")
        dpi_layout = QVBoxLayout(dpi_card)
        dpi_layout.setContentsMargins(16, 18, 16, 16)
        dpi_layout.setSpacing(12)

        # Top Bar: Add Stage + Preset Quick Select
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Configure DPI Stages (200 - 12800):"))

        btn_add = QPushButton("+ Add Stage")
        btn_add.setObjectName("primaryBtn")
        btn_add.setFixedWidth(110)
        btn_add.clicked.connect(self._add_new_stage)
        top_bar.addWidget(btn_add, 0, Qt.AlignRight)

        dpi_layout.addLayout(top_bar)

        # Scroll Area for stages
        self.stages_scroll = QScrollArea()
        self.stages_scroll.setWidgetResizable(True)
        self.stages_scroll.setFrameShape(QFrame.NoFrame)
        self.stages_scroll.setStyleSheet("background: transparent;")

        self.stages_container = QWidget()
        self.stages_layout = QVBoxLayout(self.stages_container)
        self.stages_layout.setContentsMargins(0, 0, 0, 0)
        self.stages_layout.setSpacing(10)
        self.stages_layout.addStretch()

        self.stages_scroll.setWidget(self.stages_container)
        dpi_layout.addWidget(self.stages_scroll, 1)

        # Quick Presets Buttons
        presets_bar = QHBoxLayout()
        presets_bar.addWidget(QLabel("Quick Presets:"))

        fps_btn = QPushButton("FPS (400, 800, 1600)")
        fps_btn.clicked.connect(lambda: self._apply_quick_preset([400, 800, 1600]))
        presets_bar.addWidget(fps_btn)

        balanced_btn = QPushButton("Balanced (800, 1600, 3200)")
        balanced_btn.clicked.connect(lambda: self._apply_quick_preset([800, 1600, 3200]))
        presets_bar.addWidget(balanced_btn)

        high_btn = QPushButton("High-Res (1200..8000)")
        high_btn.clicked.connect(lambda: self._apply_quick_preset([1400, 1800, 3200, 4000, 5600, 8000]))
        presets_bar.addWidget(high_btn)

        dpi_layout.addLayout(presets_bar)

        right_col.addWidget(dpi_card)
        main_layout.addLayout(right_col, 5)

    def _rebuild_stages(self, stages: List[Dict[str, Any]], active_idx: int = 0):
        # Clear existing
        for w in self._stage_widgets:
            w.deleteLater()
        self._stage_widgets.clear()

        self._active_stage_idx = active_idx

        for i, s in enumerate(stages):
            w = StageRowWidget(i, s, self)
            w.stage_changed.connect(self.changed.emit)
            w.remove_requested.connect(self._remove_stage)
            w.activated_requested.connect(self._set_active_stage)
            if i == self._active_stage_idx:
                w.radio_active.setChecked(True)

            self.stages_layout.insertWidget(len(self._stage_widgets), w)
            self._stage_widgets.append(w)

    def _add_new_stage(self):
        if len(self._stage_widgets) >= 8:
            return  # Maximum 8 custom stages
        new_dpi = 1600
        if self._stage_widgets:
            last_dpi = self._stage_widgets[-1].get_data()["dpi"]
            new_dpi = min(12800, last_dpi + 800)

        colors = [
            [255, 255, 0], [0, 80, 255], [255, 0, 200], [0, 255, 100],
            [255, 30, 30], [0, 225, 255], [255, 150, 0], [180, 0, 255]
        ]
        color = colors[len(self._stage_widgets) % len(colors)]
        new_stage = {"dpi": new_dpi, "enabled": True, "color": color}

        idx = len(self._stage_widgets)
        w = StageRowWidget(idx, new_stage, self)
        w.stage_changed.connect(self.changed.emit)
        w.remove_requested.connect(self._remove_stage)
        w.activated_requested.connect(self._set_active_stage)

        self.stages_layout.insertWidget(idx, w)
        self._stage_widgets.append(w)
        self.changed.emit()

    def _remove_stage(self, widget: StageRowWidget):
        if len(self._stage_widgets) <= 1:
            return  # Keep at least 1 stage
        if widget in self._stage_widgets:
            idx = self._stage_widgets.index(widget)
            self._stage_widgets.remove(widget)
            widget.deleteLater()

            # Renumber stages
            for i, w in enumerate(self._stage_widgets):
                w.stage_idx = i
                w.chk_enabled.setText(f"Stage {i + 1}")

            if self._active_stage_idx >= len(self._stage_widgets):
                self._active_stage_idx = max(0, len(self._stage_widgets) - 1)
            if self._stage_widgets:
                self._stage_widgets[self._active_stage_idx].radio_active.setChecked(True)

            self.changed.emit()

    def _set_active_stage(self, idx: int):
        self._active_stage_idx = idx
        for i, w in enumerate(self._stage_widgets):
            w.radio_active.blockSignals(True)
            w.radio_active.setChecked(i == idx)
            w.radio_active.blockSignals(False)
        self.changed.emit()

    def _apply_quick_preset(self, dpis: List[int]):
        colors = [
            [255, 255, 0], [0, 80, 255], [255, 0, 200],
            [0, 255, 100], [255, 30, 30], [0, 225, 255]
        ]
        stages = []
        for i, val in enumerate(dpis):
            stages.append({
                "dpi": val,
                "enabled": True,
                "color": colors[i % len(colors)],
            })
        self._rebuild_stages(stages, 0)
        self.changed.emit()

    def load_config(self, config: Dict[str, Any]):
        perf = config.get("performance", {})
        sens = perf.get("sensitivity", 6)
        self.sens_slider.setValue(sens)
        self.sens_val.setText(f"{sens} / 11")

        scroll = perf.get("scroll_speed", 4)
        self.scroll_slider.setValue(scroll)
        self.scroll_val.setText(f"{scroll} / 11")

        dc = perf.get("double_click_speed", 140)
        self.dc_slider.setValue(dc)
        self.dc_val.setText(f"{dc} ms")

        poll = perf.get("polling_rate", 500)
        btn = self.poll_group.button(poll)
        if btn:
            btn.setChecked(True)

        dpi_cfg = config.get("dpi", {})
        stages = dpi_cfg.get("stages", [
            {"dpi": 1400, "enabled": True, "color": [255, 255, 0]},
            {"dpi": 1800, "enabled": True, "color": [0, 80, 255]},
            {"dpi": 3200, "enabled": True, "color": [255, 0, 200]},
            {"dpi": 4000, "enabled": True, "color": [0, 255, 100]},
            {"dpi": 5600, "enabled": True, "color": [255, 30, 30]},
            {"dpi": 8000, "enabled": True, "color": [0, 225, 255]},
        ])
        active_idx = dpi_cfg.get("active_stage", 0)
        self._rebuild_stages(stages, active_idx)

    def save_config(self, config: Dict[str, Any]):
        if "performance" not in config:
            config["performance"] = {}
        config["performance"]["sensitivity"] = self.sens_slider.value()
        config["performance"]["scroll_speed"] = self.scroll_slider.value()
        config["performance"]["double_click_speed"] = self.dc_slider.value()
        config["performance"]["polling_rate"] = self.poll_group.checkedId()

        stages = [w.get_data() for w in self._stage_widgets]
        config["dpi"] = {
            "active_stage": self._active_stage_idx,
            "stages": stages,
        }
