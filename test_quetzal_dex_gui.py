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


def test_dexnav_1to1_route_encounters(qapp):
    win = quetzal_dex_gui.QuetzalMasterApp()

    # Verify Habitat Boxes Geometry matching authentic DexNav
    assert len(win.water_box.slots) == 5
    assert len(win.land_box.slots) == 12
    assert len(win.beach_box.slots) == 3
    assert len(win.hidden_box.slots) == 1

    # Route 101: 0 Water, 12 Land (with Lechonk), 0 Beach, 1 Hidden (Alolan Vulpix)
    win.route_combo.setCurrentText("ROUTE 101")
    assert win.dexnav_route_header.text() == "ROUTE 101"
    
    # Water has 5 empty X slots
    assert all(s.mon_data is None for s in win.water_box.slots)
    assert win.water_box.slots[0].center_box.text() == "✕"
    
    # Land has 12 slots populated
    assert all(s.mon_data is not None for s in win.land_box.slots)
    # Slot 6 is Lechonk (species_id 1244, national_dex_num 915)
    lechonk_slot = win.land_box.slots[5]
    assert lechonk_slot.species_id == 1244
    assert lechonk_slot.mon_data["species_name"] == "Lechonk"
    assert lechonk_slot.dex_num.text() == "#0915"

    # Beach has 3 empty X slots
    assert all(s.mon_data is None for s in win.beach_box.slots)
    assert win.beach_box.slots[0].center_box.text() == "✕"

    # Hidden has 1 slot: Alolan Vulpix
    vulpix_slot = win.hidden_box.slots[0]
    assert vulpix_slot.mon_data is not None
    assert vulpix_slot.species_id == 954
    assert vulpix_slot.dex_num.text() == "#0037"

    # Route 103: 5 Water, 12 Land, 0 Beach, 1 Hidden (Ditto), 0 Fishing
    win.route_combo.setCurrentText("ROUTE 103")
    assert win.dexnav_route_header.text() == "ROUTE 103"
    assert all(s.mon_data is not None for s in win.water_box.slots)
    assert win.water_box.slots[0].mon_data["species_name"] == "Clauncher"
    assert win.water_box.slots[4].mon_data["species_name"] == "Clawitzer"
    assert all(s.mon_data is not None for s in win.land_box.slots)
    assert all(s.mon_data is None for s in win.beach_box.slots)
    assert win.hidden_box.slots[0].mon_data["species_name"] == "Ditto"

    # Inspector Drawer checks
    win.water_box.slots[0].slot_selected.emit(win.water_box.slots[0].mon_data)
    assert win.inspector_drawer.current_species_id == 692
    assert "Clauncher" in win.inspector_drawer.name_lbl.text()
    assert hasattr(win.inspector_drawer, "search_btn")
    assert win.inspector_drawer.search_btn.text() == "SEARCH"
    assert "SEARCH LEVEL:" in win.inspector_drawer.search_lvl_lbl.text()
    assert "HIDDEN ABILITY:" in win.inspector_drawer.hidden_ability_lbl.text()

    win.close()


def test_authentic_gba_pokedex_view(qapp):
    from pokedex_retro_view import PokedexRetroView
    view = PokedexRetroView()
    assert view is not None
    # 1. 1025 National Pokédex Entries Loaded
    assert len(view.pokemon_by_nat) == 1025
    assert len(view.nat_nums) == 1025
    assert view.nat_nums[0] == 1
    assert view.nat_nums[-1] == 1025

    # 2. Aerodactyl (#0142) Base Stats matching Ground Truth
    assert 142 in view.pokemon_by_nat
    aero = view.pokemon_by_nat[142]
    assert aero["name"] == "Aerodactyl"
    assert aero["hp"] == 80
    assert aero["atk"] == 105
    assert aero["def"] == 65
    assert aero["spa"] == 60
    assert aero["spd"] == 75
    assert aero["spe"] == 130
    assert aero["bst"] == 515

    # Select Aerodactyl
    view.select_pokemon(142)
    assert view.current_nat == 142
    assert "0142 AERODACTYL" in view.main_name_lbl.text()
    assert "BST: 515" in view.lbl_bst.text()

    # 3. National Summary counts from Save file
    assert int(view.lbl_seen_val.text()) > 0
    assert int(view.lbl_own_val.text()) > 0
    assert "%" in view.lbl_completion.text()

    # 4. Unseen Pokémon Display
    # Find an unseen entry
    unseen_nat = next((n for n in view.nat_nums if not view.is_seen(n)), None)
    if unseen_nat:
        view.select_pokemon(unseen_nat)
        assert "-----------" in view.main_name_lbl.text()
        assert view.lbl_bst.text() == "BST: ???"

    view.close()


def test_authentic_gba_start_menu_overlay(qapp):
    from gba_start_menu_widget import GbaStartMenuOverlay
    win = quetzal_dex_gui.QuetzalMasterApp()
    win.show()
    
    # 1. Start Menu Overlay Initial State
    assert hasattr(win, "start_menu")
    assert win.start_menu is not None
    assert win.start_menu.player_name == "NIG"
    assert win.start_menu.money > 0
    assert ":" in win.start_menu.play_time

    # 2. Toggle Menu via Space / Method
    win.toggle_start_menu()
    assert win.start_menu.isVisible() is True

    # 3. Menu Items List
    menu_ids = [it["id"] for it in win.start_menu.menu_items]
    assert menu_ids == ["POKÉDEX", "DEXNAV", "TOWN MAP", "POKÉMON", "LEGENDARY", "OPTION", "MISC"]

    # 4. Action Triggering
    # Trigger POKÉDEX action
    win.start_menu.selected_index = 0
    win.start_menu.activate_selected()
    assert win.tabs.currentIndex() == 2  # Switched to Pokédex tab
    assert win.pokedex_main_tabs.currentIndex() == 0  # In-Game GBA Pokédex active

    # Trigger DEXNAV action
    win.on_start_menu_action("DEXNAV")
    assert win.tabs.currentIndex() == 0  # Switched to Route Encounters

    win.close()


def test_pokedex_retro_evos_and_paths(qapp):
    from pokedex_retro_view import PokedexRetroView, EvoNodeCard
    from PySide6.QtWidgets import QLabel
    view = PokedexRetroView()
    
    # 1. Linear chain: Charmander (#4) -> Charmeleon (#5) -> Charizard (#6)
    view.select_pokemon(4)
    view.show_evos_tab()
    assert view.current_right_tab == 1
    assert view.right_stack.currentIndex() == 1
    evo_cards = view.evos_container.findChildren(EvoNodeCard)
    evo_nats = [c.nat for c in evo_cards]
    assert evo_nats == [4, 5, 6]
    
    # 2. Branching tree: Eevee (#133) -> 8 Eeveelutions
    view.select_pokemon(133)
    eevee_cards = [c.nat for c in view.evos_container.findChildren(EvoNodeCard)]
    assert len(eevee_cards) == 9
    assert set(eevee_cards) == {133, 134, 135, 136, 196, 197, 470, 471, 700}
    
    # 3. Branching tree: Applin (#840) -> Flapple, Appletun, Dipplin -> Hydrapple
    view.select_pokemon(840)
    applin_cards = [c.nat for c in view.evos_container.findChildren(EvoNodeCard)]
    assert len(applin_cards) == 5
    
    # 4. Branching tree: Tyrogue (#236) -> Hitmonlee, Hitmonchan, Hitmontop
    view.select_pokemon(236)
    tyrogue_cards = [c.nat for c in view.evos_container.findChildren(EvoNodeCard)]
    assert len(tyrogue_cards) == 4
    
    # 5. Single non-evolving: Aerodactyl (#142) -> DOES NOT EVOLVE
    view.select_pokemon(142)
    labels = [lbl.text() for lbl in view.evos_container.findChildren(QLabel)]
    assert any("DOES NOT EVOLVE" in t for t in labels)
    
    # 6. Interactive jump: Click Jolteon (#135) in Eevee chain
    view.select_pokemon(133)
    jolteon_card = next(c for c in view.evos_container.findChildren(EvoNodeCard) if c.nat == 135)
    jolteon_card.on_click(135)
    assert view.current_nat == 135
    
    view.close()


def test_pokedex_retro_how_to_get(qapp):
    from pokedex_retro_view import PokedexRetroView
    from PySide6.QtWidgets import QLabel
    view = PokedexRetroView()
    view.show_how_to_get_tab()
    assert view.current_right_tab == 2
    assert view.right_stack.currentIndex() == 2
    
    # 1. Wild encounters: Pikachu (#25)
    view.select_pokemon(25)
    labels = [lbl.text() for lbl in view.how_container.findChildren(QLabel)]
    assert any("HOENN REGION" in t for t in labels)
    assert any("KANTO REGION" in t for t in labels)
    assert any("NEW MAUVILLE" in t for t in labels)
    
    # 2. Legendary encounter: Rayquaza (#384)
    view.select_pokemon(384)
    labels = [lbl.text() for lbl in view.how_container.findChildren(QLabel)]
    assert any("LEGENDARY" in t for t in labels)
    assert any("Sky Pillar" in t for t in labels)
    assert any("Mach Bike" in t for t in labels)
    
    # 3. Evolution-only (0 wild spawns): Charmeleon (#5)
    view.select_pokemon(5)
    labels = [lbl.text() for lbl in view.how_container.findChildren(QLabel)]
    assert any("NO WILD SPAWNS" in t for t in labels)
    assert any("Obtain by evolving #0004 Charmander" in t for t in labels)
    
    # Test jump button to pre-evolution
    view.on_pre_evo_btn_clicked(4)
    assert view.current_nat == 4
    
    # 4. Special Acquisition: Beldum (#374)
    view.select_pokemon(374)
    labels = [lbl.text() for lbl in view.how_container.findChildren(QLabel)]
    assert any("Steven's House" in t for t in labels)
    
    view.close()


def test_dexnav_jump_to_pokedex_evos_tab(qapp):
    win = quetzal_dex_gui.QuetzalMasterApp()
    
    # From Route Encounters (tab 0), select slot
    slot = win.land_box.slots[0]
    slot.slot_selected.emit(slot.mon_data)
    
    # Click DexNav inspector's View Learnset & Evolution in Pokédex button
    win.inspector_drawer.open_pokedex_btn.click()
    
    assert win.tabs.currentIndex() == 2
    assert win.pokedex_main_tabs.currentIndex() == 0
    sp_nat = win.sp_to_nat.get(slot.species_id, slot.species_id)
    assert win.retro_pokedex_view.current_nat == sp_nat
    assert win.retro_pokedex_view.current_right_tab == 1
    
    win.close()


def test_pure_gba_retro_mode_no_tabs_and_controls(qapp):
    win = quetzal_dex_gui.QuetzalMasterApp()
    win.show()
    assert win.current_theme == "retro"
    assert win.tabs.tabBar().isVisible() is False
    assert win.header_frame.isVisible() is False
    assert win.controls.isVisible() is False
    assert win.controller_guide_bar.isVisible() is True

    # Switching to modern restores them
    win.toggle_theme()
    assert win.current_theme == "modern"
    assert win.tabs.tabBar().isVisible() is True
    assert win.header_frame.isVisible() is True
    assert win.controls.isVisible() is True
    assert win.controller_guide_bar.isVisible() is False

    win.close()


def test_gba_dpad_navigation(qapp):
    win = quetzal_dex_gui.QuetzalMasterApp()
    # Route 101 has Land encounters
    win._select_dexnav_slot(1, 0, play_sound=False)
    assert win.dexnav_sel_row == 1
    assert win.dexnav_sel_col == 0
    slot_0 = win._get_dexnav_slots_grid()[1][0]
    assert slot_0.is_selected is True
    assert "SEARCH" in win.dexnav_search_lbl.text()

    # Move Down
    win._nav_dexnav_dpad(0, 1)
    assert win.dexnav_sel_row == 2
    slot_down = win._get_dexnav_slots_grid()[2][0]
    assert slot_down.is_selected is True
    assert slot_0.is_selected is False

    # Move Right
    win._nav_dexnav_dpad(1, 0)
    assert win.dexnav_sel_col == 1
    slot_right = win._get_dexnav_slots_grid()[2][1]
    assert slot_right.is_selected is True

    win.close()


def test_gba_spacebar_start_menu_event_filter(qapp):
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtCore import QEvent, Qt

    win = quetzal_dex_gui.QuetzalMasterApp()
    win.show()
    assert win.start_menu.isVisible() is False

    # Simulate Space key event through event filter
    space_ev = QKeyEvent(QEvent.KeyPress, Qt.Key_Space, Qt.NoModifier)
    consumed = win.gba_event_filter.eventFilter(win, space_ev)
    assert consumed is True
    assert win.start_menu.isVisible() is True

    # Simulate Escape key event through event filter
    esc_ev = QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
    consumed = win.gba_event_filter.eventFilter(win, esc_ev)
    assert consumed is True
    assert win.start_menu.isVisible() is False

    win.close()
