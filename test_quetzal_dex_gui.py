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
    assert win.tabs.count() == 6
    assert win.current_route_name == "ROUTE 101"
    win.close()

def test_route_encounters_data(qapp):
    win = quetzal_dex_gui.QuetzalMasterApp()
    # Route 101 has 13 encounters (12 Land + 1 Hidden Eevee)
    assert len(win.current_route_data) == 13
    eevee = next((m for m in win.current_route_data if m["species_name"] == "Eevee"), None)
    assert eevee is not None
    assert eevee["method"] == "Hidden Rare"
    win.close()

def test_legendaries_synergies(qapp):
    win = quetzal_dex_gui.QuetzalMasterApp()
    assert len(win.all_legendary_data) >= 90
    for row in win.all_legendary_data:
        name, gen, loc, req, synergy = row
        assert synergy != ""
        assert synergy is not None
    win.close()

def test_catch_calculator(qapp):
    win = quetzal_dex_gui.QuetzalMasterApp()
    # Select index 0 (Abomasnow or similar)
    win.calculate_catch_rate()
    text = win.calc_result_lbl.text()
    assert "Capture Probability" in text
    assert "%" in text
    win.close()
