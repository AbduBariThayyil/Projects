"""
Macro Management & Recording Tab for Ant Esports GM320.
Features:
- Dual-pane layout: Macro list + Event timeline.
- High-precision live recording of keyboard and mouse events with millisecond delays.
- Event insertion dialog (Key Down/Up, Mouse Click, Custom Delay).
- Execution cycle options (until released, until clicked again, repeat N times).
- Interactive Macro testing sandbox.
"""

from typing import List, Optional
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QGroupBox, QRadioButton,
    QButtonGroup, QSpinBox, QInputDialog, QMessageBox,
    QDialog, QComboBox, QLineEdit, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QIcon
from ant_gm320.core.macro_engine import Macro, MacroEvent, MacroRecorder
from ant_gm320.core.usb_hid_keys import HID_KEY_MAP


class InsertEventDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Insert Macro Event")
        self.setFixedSize(320, 240)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        layout.addWidget(QLabel("Event Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItem("Key Press (Down + Up)", "key_press")
        self.type_combo.addItem("Key Down", "key_down")
        self.type_combo.addItem("Key Up", "key_up")
        self.type_combo.addItem("Mouse Click", "mouse_click")
        self.type_combo.addItem("Delay (ms)", "delay")
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        layout.addWidget(self.type_combo)

        # Dynamic parameter row
        self.param_label = QLabel("Key:")
        layout.addWidget(self.param_label)

        self.key_input = QLineEdit("A")
        layout.addWidget(self.key_input)

        self.mouse_combo = QComboBox()
        self.mouse_combo.addItem("Left Click", "left")
        self.mouse_combo.addItem("Right Click", "right")
        self.mouse_combo.addItem("Middle Click", "middle")
        self.mouse_combo.setVisible(False)
        layout.addWidget(self.mouse_combo)

        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(1, 10000)
        self.delay_spin.setValue(50)
        self.delay_spin.setSuffix(" ms")
        self.delay_spin.setVisible(False)
        layout.addWidget(self.delay_spin)

        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        confirm_btn = QPushButton("Insert")
        confirm_btn.setObjectName("primaryBtn")
        confirm_btn.clicked.connect(self.accept)
        btn_layout.addWidget(confirm_btn)
        layout.addLayout(btn_layout)

    def _on_type_changed(self):
        t = self.type_combo.currentData()
        if t in ["key_press", "key_down", "key_up"]:
            self.param_label.setText("Key:")
            self.key_input.setVisible(True)
            self.mouse_combo.setVisible(False)
            self.delay_spin.setVisible(False)
        elif t == "mouse_click":
            self.param_label.setText("Mouse Button:")
            self.key_input.setVisible(False)
            self.mouse_combo.setVisible(True)
            self.delay_spin.setVisible(False)
        elif t == "delay":
            self.param_label.setText("Delay Duration:")
            self.key_input.setVisible(False)
            self.mouse_combo.setVisible(False)
            self.delay_spin.setVisible(True)

    def get_events(self) -> List[MacroEvent]:
        t = self.type_combo.currentData()
        if t == "key_press":
            k = self.key_input.text().strip().lower() or "a"
            return [
                MacroEvent("key_down", key=k),
                MacroEvent("delay", delay_ms=30),
                MacroEvent("key_up", key=k),
            ]
        elif t == "key_down":
            return [MacroEvent("key_down", key=self.key_input.text().strip().lower() or "a")]
        elif t == "key_up":
            return [MacroEvent("key_up", key=self.key_input.text().strip().lower() or "a")]
        elif t == "mouse_click":
            return [MacroEvent("mouse_click", button=self.mouse_combo.currentData())]
        elif t == "delay":
            return [MacroEvent("delay", delay_ms=self.delay_spin.value())]
        return []


class MacroTab(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._macros: List[Macro] = []
        self._current_macro: Optional[Macro] = None
        self._recorder = MacroRecorder(self)
        self._recorder.event_recorded.connect(self._on_live_event_recorded)
        self._setup_ui()
        self._load_sample_macros()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(24)

        # 1. Left Column: Macro List
        left_card = QGroupBox("Macro List")
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(14, 20, 14, 14)
        left_layout.setSpacing(10)

        self.macro_list_widget = QListWidget()
        self.macro_list_widget.currentRowChanged.connect(self._on_macro_selected)
        left_layout.addWidget(self.macro_list_widget, 1)

        btn_row1 = QHBoxLayout()
        btn_add = QPushButton("+ New")
        btn_add.setObjectName("primaryBtn")
        btn_add.clicked.connect(self._create_macro)
        btn_clone = QPushButton("Clone")
        btn_clone.clicked.connect(self._clone_macro)
        btn_del = QPushButton("Delete")
        btn_del.setObjectName("dangerBtn")
        btn_del.clicked.connect(self._delete_macro)
        btn_row1.addWidget(btn_add)
        btn_row1.addWidget(btn_clone)
        btn_row1.addWidget(btn_del)
        left_layout.addLayout(btn_row1)

        # Recording Button
        self.btn_record = QPushButton("● Start Recording")
        self.btn_record.setFixedHeight(38)
        self.btn_record.setCursor(Qt.PointingHandCursor)
        self.btn_record.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a2230, stop:1 #243044);
                border: 1px solid #ff3366;
                color: #ff3366;
                font-weight: 700;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: rgba(255, 51, 102, 0.2);
            }
        """)
        self.btn_record.clicked.connect(self._toggle_recording)
        left_layout.addWidget(self.btn_record)

        main_layout.addWidget(left_card, 3)

        # 2. Middle Column: Key / Event Timeline
        mid_card = QGroupBox("Event Sequence & Timings")
        mid_layout = QVBoxLayout(mid_card)
        mid_layout.setContentsMargins(14, 20, 14, 14)
        mid_layout.setSpacing(10)

        self.event_list_widget = QListWidget()
        self.event_list_widget.itemDoubleClicked.connect(self._edit_event_delay)
        mid_layout.addWidget(self.event_list_widget, 1)

        timeline_tools = QHBoxLayout()
        btn_insert = QPushButton("+ Insert Event")
        btn_insert.clicked.connect(self._insert_event)
        btn_up = QPushButton("▲ Up")
        btn_up.clicked.connect(self._move_event_up)
        btn_down = QPushButton("▼ Down")
        btn_down.clicked.connect(self._move_event_down)
        btn_remove_ev = QPushButton("✕ Remove")
        btn_remove_ev.clicked.connect(self._remove_event)

        timeline_tools.addWidget(btn_insert)
        timeline_tools.addWidget(btn_up)
        timeline_tools.addWidget(btn_down)
        timeline_tools.addWidget(btn_remove_ev)
        mid_layout.addLayout(timeline_tools)

        main_layout.addWidget(mid_card, 4)

        # 3. Right Column: Execution Cycle Options & Sandbox Test Area
        right_card = QGroupBox("Cycle Mode & Testing")
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(16, 20, 16, 16)
        right_layout.setSpacing(16)

        cycle_label = QLabel("Execution Cycle Mode:")
        cycle_label.setStyleSheet("font-weight: 700; color: #00e5ff;")
        right_layout.addWidget(cycle_label)

        self.cycle_group = QButtonGroup(self)
        self.radio_until_release = QRadioButton("Cycle until the key released")
        self.radio_until_click = QRadioButton("Cycle until the key clicked again")
        self.radio_repeat_count = QRadioButton("Specified cycle times:")

        self.radio_until_release.setChecked(True)
        self.cycle_group.addButton(self.radio_until_release, 0)
        self.cycle_group.addButton(self.radio_until_click, 1)
        self.cycle_group.addButton(self.radio_repeat_count, 2)
        self.cycle_group.idClicked.connect(self._on_cycle_mode_changed)

        right_layout.addWidget(self.radio_until_release)
        right_layout.addWidget(self.radio_until_click)

        repeat_h = QHBoxLayout()
        repeat_h.addWidget(self.radio_repeat_count)
        self.repeat_spin = QSpinBox()
        self.repeat_spin.setRange(1, 1000)
        self.repeat_spin.setValue(3)
        self.repeat_spin.setFixedWidth(80)
        self.repeat_spin.valueChanged.connect(self._on_repeat_count_changed)
        repeat_h.addWidget(self.repeat_spin)
        right_layout.addLayout(repeat_h)

        right_layout.addSpacing(10)

        # Sandbox Test Box
        test_label = QLabel("Interactive Macro Test Sandbox:")
        test_label.setStyleSheet("font-weight: 700; color: #f0f6fc;")
        right_layout.addWidget(test_label)

        self.test_box = QLineEdit()
        self.test_box.setPlaceholderText("Click here to test typing or live recording...")
        self.test_box.setFixedHeight(40)
        right_layout.addWidget(self.test_box)

        btn_run_test = QPushButton("▶ Run Macro in Sandbox")
        btn_run_test.setFixedHeight(34)
        btn_run_test.clicked.connect(self._run_macro_in_sandbox)
        right_layout.addWidget(btn_run_test)

        right_layout.addStretch(1)
        main_layout.addWidget(right_card, 3)

    def _load_sample_macros(self):
        m1 = Macro(
            name="Rapid Triple Click",
            events=[
                MacroEvent("mouse_click", button="left"),
                MacroEvent("delay", delay_ms=40),
                MacroEvent("mouse_click", button="left"),
                MacroEvent("delay", delay_ms=40),
                MacroEvent("mouse_click", button="left"),
            ],
            cycle_mode="until_released"
        )
        m2 = Macro(
            name="FPS Quick Jump",
            events=[
                MacroEvent("key_down", key="space"),
                MacroEvent("delay", delay_ms=30),
                MacroEvent("key_up", key="space"),
                MacroEvent("delay", delay_ms=50),
                MacroEvent("key_down", key="ctrl"),
                MacroEvent("delay", delay_ms=30),
                MacroEvent("key_up", key="ctrl"),
            ],
            cycle_mode="repeat_count",
            repeat_count=1
        )
        self._macros = [m1, m2]
        self._refresh_macro_list()

    def _refresh_macro_list(self):
        self.macro_list_widget.clear()
        for m in self._macros:
            self.macro_list_widget.addItem(m.name)
        if self._macros:
            self.macro_list_widget.setCurrentRow(0)

    def _on_macro_selected(self, row: int):
        if 0 <= row < len(self._macros):
            self._current_macro = self._macros[row]
            self._display_events(self._current_macro)
            self._update_cycle_options(self._current_macro)

    def _display_events(self, macro: Macro):
        self.event_list_widget.clear()
        for e in macro.events:
            item = QListWidgetItem(e.display_text())
            if e.event_type == "delay":
                item.setForeground(Qt.darkGray)
            elif e.event_type == "mouse_click":
                item.setForeground(Qt.cyan)
            else:
                item.setForeground(Qt.white)
            self.event_list_widget.addItem(item)

    def _update_cycle_options(self, macro: Macro):
        if macro.cycle_mode == "until_released":
            self.radio_until_release.setChecked(True)
        elif macro.cycle_mode == "until_clicked_again":
            self.radio_until_click.setChecked(True)
        else:
            self.radio_repeat_count.setChecked(True)
        self.repeat_spin.setValue(macro.repeat_count)

    def _on_cycle_mode_changed(self, mode_id: int):
        if not self._current_macro:
            return
        if mode_id == 0:
            self._current_macro.cycle_mode = "until_released"
        elif mode_id == 1:
            self._current_macro.cycle_mode = "until_clicked_again"
        elif mode_id == 2:
            self._current_macro.cycle_mode = "repeat_count"
        self.changed.emit()

    def _on_repeat_count_changed(self, val: int):
        if self._current_macro:
            self._current_macro.repeat_count = val
            self.changed.emit()

    def _create_macro(self):
        name, ok = QInputDialog.getText(self, "New Macro", "Enter macro name:")
        if ok and name.strip():
            m = Macro(name=name.strip())
            self._macros.append(m)
            self._refresh_macro_list()
            self.macro_list_widget.setCurrentRow(len(self._macros) - 1)
            self.changed.emit()

    def _clone_macro(self):
        if not self._current_macro:
            return
        import copy
        new_m = copy.deepcopy(self._current_macro)
        new_m.name += " (Copy)"
        self._macros.append(new_m)
        self._refresh_macro_list()
        self.macro_list_widget.setCurrentRow(len(self._macros) - 1)
        self.changed.emit()

    def _delete_macro(self):
        if not self._current_macro:
            return
        if len(self._macros) <= 1:
            QMessageBox.information(self, "Macro", "At least one macro must remain in the list.")
            return
        self._macros.remove(self._current_macro)
        self._refresh_macro_list()
        self.changed.emit()

    def _toggle_recording(self):
        if not self._current_macro:
            return

        if not self._recorder.is_recording:
            # Start
            self._current_macro.events.clear()
            self.event_list_widget.clear()
            self._recorder.start_recording()
            self.btn_record.setText("■ Stop Recording")
            self.btn_record.setStyleSheet("""
                QPushButton {
                    background-color: #ff3366;
                    border: none;
                    color: #ffffff;
                    font-weight: 700;
                    border-radius: 6px;
                }
            """)
            self.test_box.setFocus()
        else:
            # Stop
            events = self._recorder.stop_recording()
            self._current_macro.events = events
            self._display_events(self._current_macro)
            self.btn_record.setText("● Start Recording")
            self.btn_record.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a2230, stop:1 #243044);
                    border: 1px solid #ff3366;
                    color: #ff3366;
                    font-weight: 700;
                    border-radius: 6px;
                }
            """)
            self.changed.emit()

    def _on_live_event_recorded(self, ev: MacroEvent):
        if self._current_macro:
            self._current_macro.events.append(ev)
            item = QListWidgetItem(ev.display_text())
            if ev.event_type == "delay":
                item.setForeground(Qt.darkGray)
            elif ev.event_type == "mouse_click":
                item.setForeground(Qt.cyan)
            self.event_list_widget.addItem(item)
            self.event_list_widget.scrollToBottom()

    def keyPressEvent(self, event: QKeyEvent):
        if self._recorder.is_recording:
            k = event.text().strip() or event.keyCombination().key().name
            self._recorder.record_key_event("key_down", k)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        if self._recorder.is_recording:
            k = event.text().strip() or event.keyCombination().key().name
            self._recorder.record_key_event("key_up", k)
        super().keyReleaseEvent(event)

    def _insert_event(self):
        if not self._current_macro:
            return
        dlg = InsertEventDialog(self)
        if dlg.exec() == QDialog.Accepted:
            new_events = dlg.get_events()
            row = self.event_list_widget.currentRow()
            if row < 0:
                self._current_macro.events.extend(new_events)
            else:
                for idx, ev in enumerate(new_events):
                    self._current_macro.events.insert(row + 1 + idx, ev)
            self._display_events(self._current_macro)
            self.changed.emit()

    def _move_event_up(self):
        if not self._current_macro:
            return
        row = self.event_list_widget.currentRow()
        if row > 0:
            e = self._current_macro.events.pop(row)
            self._current_macro.events.insert(row - 1, e)
            self._display_events(self._current_macro)
            self.event_list_widget.setCurrentRow(row - 1)
            self.changed.emit()

    def _move_event_down(self):
        if not self._current_macro:
            return
        row = self.event_list_widget.currentRow()
        if 0 <= row < len(self._current_macro.events) - 1:
            e = self._current_macro.events.pop(row)
            self._current_macro.events.insert(row + 1, e)
            self._display_events(self._current_macro)
            self.event_list_widget.setCurrentRow(row + 1)
            self.changed.emit()

    def _remove_event(self):
        if not self._current_macro:
            return
        row = self.event_list_widget.currentRow()
        if 0 <= row < len(self._current_macro.events):
            self._current_macro.events.pop(row)
            self._display_events(self._current_macro)
            self.changed.emit()

    def _edit_event_delay(self, item: QListWidgetItem):
        row = self.event_list_widget.row(item)
        if 0 <= row < len(self._current_macro.events):
            ev = self._current_macro.events[row]
            if ev.event_type == "delay":
                val, ok = QInputDialog.getInt(self, "Edit Delay", "Delay in milliseconds:", ev.delay_ms, 1, 10000)
                if ok:
                    ev.delay_ms = val
                    item.setText(ev.display_text())
                    self.changed.emit()

    def _run_macro_in_sandbox(self):
        if not self._current_macro:
            return
        text = ""
        for e in self._current_macro.events:
            if e.event_type == "key_down":
                text += e.key.upper()
            elif e.event_type == "mouse_click":
                text += f"[{e.button.upper()} CLICK]"
        self.test_box.setText(text)

    def load_config(self, config_macros: List[dict]):
        if config_macros:
            self._macros = [Macro.from_dict(m) for m in config_macros]
            self._refresh_macro_list()

    def get_macros(self) -> List[dict]:
        return [m.to_dict() for m in self._macros]
