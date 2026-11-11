import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from PySide6.QtGui import QPixmap

import quetzal_dex_gui

def main():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    win = quetzal_dex_gui.QuetzalMasterApp()
    win.show()
    app.processEvents()

    # Select Route 101 to display Lechonk and Alolan Vulpix
    win.route_combo.setCurrentText("ROUTE 101")
    app.processEvents()

    # Select Lechonk slot (Land Slot 6)
    lechonk_slot = win.land_box.slots[5]
    if lechonk_slot.mon_data:
        win.on_encounter_card_clicked(lechonk_slot.mon_data)
    app.processEvents()

    # Grab pixmap of the entire window
    pixmap = win.grab()
    out_path = "verify_1to1_dexnav_layout.png"
    pixmap.save(out_path)
    print(f"Saved screenshot to {out_path} ({pixmap.width()}x{pixmap.height()})")

    # Also render Route 103 view to verify water slots
    win.route_combo.setCurrentText("ROUTE 103")
    app.processEvents()
    if win.water_box.slots[0].mon_data:
        win.on_encounter_card_clicked(win.water_box.slots[0].mon_data)
    app.processEvents()
    out_path_103 = "verify_1to1_dexnav_route103.png"
    win.grab().save(out_path_103)
    print(f"Saved screenshot to {out_path_103}")

    win.close()

if __name__ == "__main__":
    main()
