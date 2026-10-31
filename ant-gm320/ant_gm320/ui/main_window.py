"""
Main Window for Ant Esports GM320 Linux Native Application.
Orchestrates tab navigation, profile switching, hardware flashing,
live audio reactive sync, and hardware connection monitoring.
"""

import os
import sys
from typing import Optional
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QStackedWidget, QFileDialog, QMessageBox,
    QProgressBar, QFrame, QButtonGroup, QInputDialog
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QFont

from ant_gm320.core.driver import GM320Driver
from ant_gm320.core.config import ConfigManager
from ant_gm320.core.audio_sync import AudioSyncWorker
from ant_gm320.ui.theme import STYLE_SHEET, COLOR_CYAN_NEON
from ant_gm320.ui.button_tab import ButtonTab
from ant_gm320.ui.macro_tab import MacroTab
from ant_gm320.ui.performance_tab import PerformanceTab
from ant_gm320.ui.backlight_tab import BacklightTab
from ant_gm320.ui.music_tab import MusicTab


ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
APP_ICON_PATH = os.path.join(ASSETS_DIR, "app_icon.png")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ant Esports GM320 RGB - Gaming Mouse Master Control")
        if os.path.exists(APP_ICON_PATH):
            self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.resize(1024, 760)
        self.setMinimumSize(940, 680)

        # Apply dark cyberpunk theme
        self.setStyleSheet(STYLE_SHEET)

        # Core engines
        self.driver = GM320Driver()
        self.config_mgr = ConfigManager()
        self.audio_worker = AudioSyncWorker(self.driver, self)

        # UI state
        self._has_unapplied_changes = False

        self._setup_ui()
        self._setup_audio_connections()
        self._setup_device_monitor()

        # Load active profile into tabs
        self._load_active_profile()

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Header Bar: Logo, Model, Status Pill
        header = QFrame()
        header.setObjectName("app_header")
        header.setFixedHeight(64)
        header.setStyleSheet("QFrame#app_header { background-color: #0b0e14; border-bottom: 1px solid #1c2432; }")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(20, 0, 20, 0)
        h_layout.setSpacing(18)

        # Ant Esports Brand Title
        brand_v = QVBoxLayout()
        brand_v.setSpacing(1)
        brand_title = QLabel("ANT ESPORTS")
        brand_title.setStyleSheet("font-size: 17px; font-weight: 900; letter-spacing: 2px; color: #ffffff;")
        brand_sub = QLabel("GM320 RGB  |  NATIVE LINUX CONTROLLER")
        brand_sub.setStyleSheet("font-size: 11px; font-weight: 700; letter-spacing: 1.2px; color: #00e5ff;")
        brand_v.addWidget(brand_title)
        brand_v.addWidget(brand_sub)
        h_layout.addLayout(brand_v)

        h_layout.addSpacing(20)

        # Navigation Bar Buttons
        self.nav_group = QButtonGroup(self)
        nav_items = [
            ("Button", 0),
            ("Macro", 1),
            ("Performance", 2),
            ("Backlight", 3),
            ("♫ Music Sync", 4),
        ]

        nav_h = QHBoxLayout()
        nav_h.setSpacing(6)
        for label, idx in nav_items:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(38)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #8b949e;
                    border: none;
                    border-bottom: 3px solid transparent;
                    border-radius: 0;
                    padding: 0 16px;
                    font-size: 13px;
                    font-weight: 700;
                    min-width: 80px;
                }
                QPushButton:hover {
                    color: #ffffff;
                    background-color: rgba(255, 255, 255, 0.04);
                }
                QPushButton:checked {
                    color: #00e5ff;
                    border-bottom: 3px solid #00e5ff;
                    background-color: rgba(0, 229, 255, 0.08);
                }
            """)
            self.nav_group.addButton(btn, idx)
            nav_h.addWidget(btn)

        self.nav_group.idClicked.connect(self._on_nav_tab_clicked)
        h_layout.addLayout(nav_h)

        h_layout.addStretch(1)

        # Connection Status Pill
        self.status_pill = QLabel("● Connected")
        self.status_pill.setFixedHeight(28)
        self.status_pill.setStyleSheet("""
            background-color: rgba(0, 245, 155, 0.12);
            color: #00f59b;
            border: 1px solid rgba(0, 245, 155, 0.3);
            border-radius: 14px;
            padding: 0 12px;
            font-size: 11px;
            font-weight: 700;
        """)
        h_layout.addWidget(self.status_pill)

        root_layout.addWidget(header)

        # 2. Main Content Stack
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background-color: #0d1117;")

        self.button_tab = ButtonTab()
        self.macro_tab = MacroTab()
        self.perf_tab = PerformanceTab()
        self.backlight_tab = BacklightTab()
        self.music_tab = MusicTab()

        self.stack.addWidget(self.button_tab)       # 0
        self.stack.addWidget(self.macro_tab)        # 1
        self.stack.addWidget(self.perf_tab)         # 2
        self.stack.addWidget(self.backlight_tab)    # 3
        self.stack.addWidget(self.music_tab)        # 4

        # Tab change signals to track unapplied edits
        self.button_tab.changed.connect(self._mark_changed)
        self.perf_tab.changed.connect(self._mark_changed)
        self.backlight_tab.changed.connect(self._mark_changed)
        self.macro_tab.changed.connect(self._mark_changed)

        # Music shortcut from button tab
        self.button_tab.open_music_requested.connect(lambda: self._select_tab(4))

        root_layout.addWidget(self.stack, 1)

        # 3. Bottom Profiles & Action Bar
        footer = QFrame()
        footer.setObjectName("app_footer")
        footer.setFixedHeight(72)
        footer.setStyleSheet("QFrame#app_footer { background-color: #0b0e14; border-top: 1px solid #1c2432; }")
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(20, 0, 20, 0)
        f_layout.setSpacing(14)

        # Profiles bar on left
        prof_label = QLabel("Profiles:")
        prof_label.setStyleSheet("color: #8b949e; font-weight: 700; font-size: 11px; text-transform: uppercase;")
        f_layout.addWidget(prof_label)

        self.profile_buttons_layout = QHBoxLayout()
        self.profile_buttons_layout.setSpacing(6)
        self.profile_group = QButtonGroup(self)
        self.profile_group.idClicked.connect(self._on_profile_button_clicked)
        f_layout.addLayout(self.profile_buttons_layout)

        btn_new_prof = QPushButton("+")
        btn_new_prof.setFixedSize(28, 28)
        btn_new_prof.setToolTip("Add new profile")
        btn_new_prof.setStyleSheet("""
            QPushButton {
                background-color: #161b24;
                border: 1px solid #273142;
                border-radius: 6px;
                color: #00e5ff;
                font-size: 16px;
                font-weight: 700;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: rgba(0, 229, 255, 0.15);
                border-color: #00e5ff;
            }
        """)
        btn_new_prof.clicked.connect(self._create_profile)
        f_layout.addWidget(btn_new_prof)

        f_layout.addSpacing(16)

        # Profile Tools: Import, Export, Reset
        btn_import = QPushButton("Import")
        btn_import.clicked.connect(self._import_profile)
        btn_export = QPushButton("Export")
        btn_export.clicked.connect(self._export_profile)
        btn_reset = QPushButton("Reset Defaults")
        btn_reset.clicked.connect(self._reset_defaults)

        f_layout.addWidget(btn_import)
        f_layout.addWidget(btn_export)
        f_layout.addWidget(btn_reset)

        f_layout.addStretch(1)

        # Status feedback text
        self.feedback_lbl = QLabel("")
        self.feedback_lbl.setStyleSheet("color: #00f59b; font-weight: 600; font-size: 12px;")
        f_layout.addWidget(self.feedback_lbl)

        # Actions: Cancel & Apply
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFixedSize(90, 36)
        self.btn_cancel.clicked.connect(self._load_active_profile)
        f_layout.addWidget(self.btn_cancel)

        self.btn_apply = QPushButton("Apply Changes")
        self.btn_apply.setFixedSize(140, 36)
        self.btn_apply.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00b4d8, stop:1 #00e5ff);
                color: #050a12;
                border: none;
                border-radius: 6px;
                font-weight: 700;
                font-size: 13px;
                padding: 0 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00c6eb, stop:1 #33ecff);
            }
            QPushButton:disabled {
                background-color: #1e2634;
                color: #586069;
            }
        """)
        self.btn_apply.clicked.connect(self._apply_to_mouse)
        f_layout.addWidget(self.btn_apply)

        root_layout.addWidget(footer)

        # Default to Button Tab (0)
        self._select_tab(0)
        self._rebuild_profile_buttons()

    def _select_tab(self, idx: int):
        self.stack.setCurrentIndex(idx)
        btn = self.nav_group.button(idx)
        if btn:
            btn.setChecked(True)

    def _on_nav_tab_clicked(self, idx: int):
        self.stack.setCurrentIndex(idx)

    def _mark_changed(self):
        self._has_unapplied_changes = True
        self.btn_apply.setText("Apply Changes *")

    def _rebuild_profile_buttons(self):
        # Clear existing buttons in group
        for btn in self.profile_group.buttons():
            self.profile_group.removeButton(btn)
            btn.deleteLater()

        for idx, name in enumerate(self.config_mgr.profiles.keys()):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setFixedHeight(30)
            btn.setMinimumWidth(74)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #161b24;
                    border: 1px solid #273142;
                    border-radius: 6px;
                    color: #8b949e;
                    padding: 0 12px;
                    font-weight: 600;
                    font-size: 11px;
                }
                QPushButton:checked {
                    border: 1px solid #00e5ff;
                    color: #00e5ff;
                    background-color: rgba(0, 229, 255, 0.12);
                }
            """)
            if name == self.config_mgr.active_profile_name:
                btn.setChecked(True)
            self.profile_group.addButton(btn, idx)
            self.profile_buttons_layout.addWidget(btn)

    def _on_profile_button_clicked(self, idx: int):
        btn = self.profile_group.button(idx)
        if btn:
            name = btn.text()
            self.config_mgr.set_active_profile(name)
            self._load_active_profile()
            self._show_feedback(f"Switched to profile '{name}'")

    def _load_active_profile(self):
        prof = self.config_mgr.current_profile
        self.button_tab.load_config(prof)
        self.perf_tab.load_config(prof)
        self.backlight_tab.load_config(prof)
        self.macro_tab.load_config(self.config_mgr.macros)
        self._has_unapplied_changes = False
        self.btn_apply.setText("Apply Changes")

    def _create_profile(self):
        name, ok = QInputDialog.getText(self, "New Profile", "Enter new profile name:")
        if ok and name.strip():
            self.config_mgr.add_profile(name.strip(), clone_from=self.config_mgr.active_profile_name)
            self._rebuild_profile_buttons()
            self._load_active_profile()
            self._show_feedback(f"Created profile '{name.strip()}'")

    def _import_profile(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Profile or Config", "",
            "All Supported Configs (*.json *.ini);;OEM INI Files (*.ini);;JSON Profiles (*.json);;All Files (*)"
        )
        if path:
            ok, msg = self.config_mgr.import_profile(path)
            if ok:
                self._rebuild_profile_buttons()
                self._load_active_profile()
                self._show_feedback(msg)
            else:
                QMessageBox.warning(self, "Import Failed", msg)

    def _export_profile(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Profile", f"{self.config_mgr.active_profile_name}.json",
            "JSON Profiles (*.json);;OEM INI Files (*.ini);;All Files (*)"
        )
        if path:
            self.config_mgr.export_profile(path)
            self._show_feedback(f"Profile saved to {os.path.basename(path)}")

    def _reset_defaults(self):
        ret = QMessageBox.question(self, "Reset Defaults", "Reset all mouse settings and profiles to factory defaults?",
                                   QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            self.config_mgr.reset_to_defaults()
            self._rebuild_profile_buttons()
            self._load_active_profile()
            self._show_feedback("Factory defaults restored")

    def _apply_to_mouse(self):
        # Save current UI state into profile model
        prof = self.config_mgr.current_profile
        self.button_tab.save_config(prof)
        self.perf_tab.save_config(prof)
        self.backlight_tab.save_config(prof)
        self.config_mgr.macros = self.macro_tab.get_macros()
        self.config_mgr.save()

        # Burn EEPROM image into mouse hardware
        self.btn_apply.setEnabled(False)
        self.btn_apply.setText("Writing EEPROM...")
        self.feedback_lbl.setText("Flashing settings to mouse...")

        QTimer.singleShot(50, self._do_hardware_flash)

    def _do_hardware_flash(self):
        prof = self.config_mgr.current_profile
        ok, msg = self.driver.apply_configuration(prof)
        self.btn_apply.setEnabled(True)
        self.btn_apply.setText("Apply Changes")

        if ok:
            self._has_unapplied_changes = False
            self._show_feedback("✓ Settings burned to mouse EEPROM!")
        else:
            self.feedback_lbl.setText("")
            QMessageBox.warning(self, "Mouse Flash Error", msg)

    def _show_feedback(self, text: str):
        self.feedback_lbl.setText(text)
        QTimer.singleShot(3500, lambda: self.feedback_lbl.setText(""))

    def _setup_audio_connections(self):
        # Hook up MusicTab with AudioSyncWorker
        self.music_tab.sync_toggled.connect(self._handle_audio_sync_toggled)
        self.music_tab.mode_changed.connect(self.audio_worker.set_mode)
        self.music_tab.gain_changed.connect(self.audio_worker.set_gain)
        self.music_tab.colors_changed.connect(self.audio_worker.set_colors)

        self.audio_worker.metrics_updated.connect(self.music_tab.handle_audio_metrics)
        self.audio_worker.beat_detected.connect(self.music_tab.handle_beat_detected)

    def _handle_audio_sync_toggled(self, active: bool):
        if active:
            if not self.audio_worker.isRunning():
                self.audio_worker.start()
        else:
            if self.audio_worker.isRunning():
                self.audio_worker.stop()

    def _setup_device_monitor(self):
        self._dev_timer = QTimer(self)
        self._dev_timer.timeout.connect(self._check_device_status)
        self._dev_timer.start(2500)
        self._check_device_status()

    def _check_device_status(self):
        status, path = self.driver.get_status()
        if status == "ok":
            self.status_pill.setText(f"● Connected ({path})")
            self.status_pill.setToolTip(f"Device connected and ready on {path}")
            self.status_pill.setStyleSheet("""
                background-color: rgba(0, 245, 155, 0.12);
                color: #00f59b;
                border: 1px solid rgba(0, 245, 155, 0.3);
                border-radius: 14px;
                padding: 0 12px;
                font-size: 11px;
                font-weight: 700;
            """)
        elif status == "permission_denied":
            self.status_pill.setText(f"⚠ Permission Denied ({path})")
            self.status_pill.setToolTip("Run: sudo chmod 666 /dev/hidraw* to grant access, or update udev rule.")
            self.status_pill.setStyleSheet("""
                background-color: rgba(255, 179, 0, 0.15);
                color: #ffb300;
                border: 1px solid rgba(255, 179, 0, 0.4);
                border-radius: 14px;
                padding: 0 12px;
                font-size: 11px;
                font-weight: 700;
            """)
        else:
            self.status_pill.setText("○ Mouse Disconnected")
            self.status_pill.setToolTip("Please connect the GM320 USB cable")
            self.status_pill.setStyleSheet("""
                background-color: rgba(255, 51, 102, 0.12);
                color: #ff3366;
                border: 1px solid rgba(255, 51, 102, 0.3);
                border-radius: 14px;
                padding: 0 12px;
                font-size: 11px;
                font-weight: 700;
            """)

    def closeEvent(self, event):
        if self.audio_worker.isRunning():
            self.audio_worker.stop()
        try:
            self.driver.restore_hardware_mode()
        except Exception:
            pass
        super().closeEvent(event)
