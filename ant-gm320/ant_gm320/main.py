"""
Main entry point for Ant Esports GM320 Gaming Mouse Master Control.
"""

import sys
import os

# Ensure package root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from ant_gm320.ui.main_window import MainWindow

ASSET_ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "mouse_transparent.png")


def main():
    # Enable High DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    app.setApplicationName("Ant Esports GM320 Master Control")
    app.setOrganizationName("AntEsportsLinux")

    if os.path.exists(ASSET_ICON_PATH):
        app.setWindowIcon(QIcon(ASSET_ICON_PATH))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
