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

def test_pokedex_national_dex_database():
    import sqlite3
    conn = sqlite3.connect("quetzal_database.db")
    cur = conn.cursor()
    cur.execute("SELECT national_dex_num, name, type1 FROM pokemon WHERE id IN (37, 954) ORDER BY id")
    rows = cur.fetchall()
    assert rows == [(37, "Vulpix", "Fire"), (37, "Vulpix", "Ice")]

    # Meowth forms
    cur.execute("SELECT DISTINCT national_dex_num FROM pokemon WHERE id IN (52, 958, 967, 1440)")
    assert cur.fetchall() == [(52,)]

    # Ponyta forms
    cur.execute("SELECT DISTINCT national_dex_num FROM pokemon WHERE id IN (77, 968)")
    assert cur.fetchall() == [(77,)]

    # Zorua forms
    cur.execute("SELECT DISTINCT national_dex_num FROM pokemon WHERE id IN (570, 1233)")
    assert cur.fetchall() == [(570,)]

    # Mega Latios
    cur.execute("SELECT DISTINCT national_dex_num FROM pokemon WHERE id IN (381, 938)")
    assert cur.fetchall() == [(381,)]

    # Lechonk
    cur.execute("SELECT national_dex_num FROM pokemon WHERE id = 1244")
    assert cur.fetchone() == (915,)
    conn.close()

def test_encounter_card_national_dex_display(qapp):
    win = quetzal_dex_gui.QuetzalMasterApp()
    vulpix_card = None
    for card in win.all_rendered_cards:
        if card.species_id == 954:
            vulpix_card = card
            break
    assert vulpix_card is not None
    assert vulpix_card.dex_num.text() == "#0037"
    assert vulpix_card.form_badge == "Alolan"
    assert hasattr(vulpix_card, "form_badge_lbl")
    assert "Alolan Form" in vulpix_card.form_badge_lbl.text()
    win.close()

def test_pokedex_tab_form_grouping_and_search(qapp):
    win = quetzal_dex_gui.QuetzalMasterApp()
    
    # 1. Search for 37
    win.filter_pokedex_list("37")
    visible_items = [win.pokedex_list.item(i) for i in range(win.pokedex_list.count()) if not win.pokedex_list.item(i).isHidden()]
    assert len(visible_items) == 2
    assert any("#0037 Vulpix" in it.text() for it in visible_items)
    assert any("Alolan Vulpix" in it.text() for it in visible_items)

    # 2. Search for Vulpix
    win.filter_pokedex_list("Vulpix")
    visible_items = [win.pokedex_list.item(i) for i in range(win.pokedex_list.count()) if not win.pokedex_list.item(i).isHidden()]
    assert len(visible_items) == 2

    # 3. Form inspection & Form Chips
    alolan_idx = next(i for i in range(win.pokedex_list.count()) if "Alolan Vulpix" in win.pokedex_list.item(i).text())
    win.on_pokedex_mon_selected(alolan_idx)
    assert win.current_pokedex_mon_id == 954
    assert win.current_national_dex_num == 37
    assert "#0037 Vulpix" in win.pokedex_name_lbl.text()
    assert "Alolan Form" in win.pokedex_name_lbl.text()
    assert win.pokedex_forms_layout.count() >= 2  # Standard and Alolan chips
    win.close()

def test_save_reader_national_dex_sync():
    import quetzal_save_reader
    parser = quetzal_save_reader.QuetzalSaveParser()
    caught = parser.get_all_caught_species()
    # Bit 37 is set in save file -> both 37 (Vulpix) and 954 (Alolan Vulpix) are caught
    assert 37 in caught
    assert 954 in caught
    # Bit 52 is set in save file -> both standard and forms are caught
    assert 52 in caught
    assert 958 in caught
    assert 967 in caught

