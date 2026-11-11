import os
import sys
import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, "/home/vibecoder/Projects")
import quetzal_dex_gui

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

def test_app_initialization(qapp):
    win = quetzal_dex_gui.QuetzalMasterApp()
    assert win is not None
    assert win.tabs.count() == 7
    assert win.current_route_name == "ROUTE 101"
    win.close()

def test_route_encounters_data(qapp):
    win = quetzal_dex_gui.QuetzalMasterApp()
    # Route 101 has 13 encounters (12 Land + 1 Hidden Vulpix)
    assert len(win.current_route_data) == 13
    vulpix = next((m for m in win.current_route_data if m["species_name"] == "Vulpix"), None)
    assert vulpix is not None
    assert vulpix["method"] == "Hidden Rare"
    assert vulpix["species_id"] == 954
    assert vulpix["type1"] == "Ice"
    win.close()

def test_legendaries_synergies(qapp):
    win = quetzal_dex_gui.QuetzalMasterApp()
    assert len(win.all_legendary_data) >= 90
    for item in win.all_legendary_data:
        assert isinstance(item, dict)
        assert "name" in item
        assert "generation" in item
        assert "location" in item
        assert "requirements" in item
        assert "synergy" in item
        assert item["synergy"] != ""
        assert item["synergy"] is not None
    win.close()

def test_catch_calculator(qapp):
    win = quetzal_dex_gui.QuetzalMasterApp()
    # Select index 0 (Abomasnow or similar)
    win.calculate_catch_rate()
    text = win.calc_result_lbl.text()
    assert "Capture Probability" in text
    assert "%" in text
    win.close()

def test_littleroot_town_peaceful_empty(qapp):
    win = quetzal_dex_gui.QuetzalMasterApp()
    win.on_map_route_selected("Littleroot Town", "Hoenn")
    assert win.current_route_name == "LITTLEROOT TOWN"
    assert len(win.current_route_data) == 0
    
    # Check that peaceful town message is displayed
    found_msg = False
    for i in range(win.cards_grid.count()):
        widget = win.cards_grid.itemAt(i).widget()
        if widget and hasattr(widget, "text") and "No wild Pokémon encounters in this peaceful town." in widget.text():
            found_msg = True
            break
    assert found_msg is True
    win.close()
