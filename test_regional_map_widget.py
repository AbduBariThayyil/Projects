import pytest
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPointF
from regional_map_widget import (
    RegionalMapWidget, MapCanvas, normalize_loc,
    REGION_HOENN, REGION_JOHTO, REGION_KANTO, REGION_SEVII, ALL_REGIONS,
    REGIONAL_MAP_DATA
)

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    return app

def test_normalization():
    assert normalize_loc("Route 101") == "ROUTE 101"
    assert normalize_loc("route 101") == "ROUTE 101"
    assert normalize_loc("  Route 104  ") == "ROUTE 104"
    assert normalize_loc("Route 17 (Cycling Road)") == "ROUTE 17"
    assert normalize_loc("Pokémon Mansion") == "POKEMON MANSION"
    assert normalize_loc("") == ""

def test_topology_integrity():
    for region in ALL_REGIONS:
        data = REGIONAL_MAP_DATA[region]
        nodes = data["nodes"]
        edges = data["edges"]
        assert len(nodes) > 0, f"{region} has no nodes"
        assert len(edges) > 0, f"{region} has no edges"

        for edge in edges:
            src, dst = edge[0], edge[1]
            assert src in nodes, f"Edge src '{src}' not found in {region} nodes"
            assert dst in nodes, f"Edge dst '{dst}' not found in {region} nodes"

def test_widget_initialization(qapp):
    widget = RegionalMapWidget()
    assert widget.canvas.region == REGION_HOENN
    assert len(widget.region_buttons) == 4

def test_region_switching(qapp):
    widget = RegionalMapWidget()
    for r in ALL_REGIONS:
        widget.set_region(r)
        assert widget.canvas.region == r

def test_caught_data_setting(qapp):
    widget = RegionalMapWidget()
    test_data = {
        "Route 101": (12, 12),
        "Route 102": (5, 17),
        "Petalburg City": (0, 0),
    }
    widget.set_caught_data(test_data)
    assert widget.canvas.caught_stats["ROUTE 101"] == (12, 12)
    assert widget.canvas.caught_stats["ROUTE 102"] == (5, 17)
    assert widget.canvas._get_status("Route 101") == "complete"
    assert widget.canvas._get_status("Route 102") == "partial"
    assert widget.canvas._get_status("Petalburg City") == "uncaught"

def test_highlight_locations(qapp):
    widget = RegionalMapWidget()
    widget.highlight_locations(["Route 101", "Petalburg Woods"])
    assert "ROUTE 101" in widget.canvas.highlighted_nodes
    assert "PETALBURG WOODS" in widget.canvas.highlighted_nodes

    widget.clear_highlights()
    assert len(widget.canvas.highlighted_nodes) == 0

def test_signals_emission(qapp):
    widget = RegionalMapWidget()
    received = []

    def on_route_selected(name, region):
        received.append((name, region))

    widget.route_selected.connect(on_route_selected)

    # Click on Littleroot Town
    node_data = REGIONAL_MAP_DATA[REGION_HOENN]["nodes"]["Littleroot Town"]
    px, py = widget.canvas.get_node_screen_pos(node_data["x"], node_data["y"])
    
    # Simulate canvas node clicked
    widget.canvas.node_clicked.emit("Littleroot Town", REGION_HOENN)
    assert len(received) == 1
    assert received[0] == ("Littleroot Town", REGION_HOENN)

def test_db_loading(qapp):
    widget = RegionalMapWidget()
    if sys.platform != "win32":
        widget.load_data_from_db("quetzal_database.db")
        # Should have loaded stats
        assert len(widget.canvas.caught_stats) > 0
        assert "ROUTE 101" in widget.canvas.caught_stats
        assert "PETALBURG WOODS" in widget.canvas.caught_stats
        assert len(widget.canvas.trainers_by_loc) > 0

def test_pan_and_zoom(qapp):
    widget = RegionalMapWidget()
    initial_zoom = widget.canvas.zoom_factor
    widget.canvas.zoom_in()
    assert widget.canvas.zoom_factor > initial_zoom
    widget.canvas.zoom_out()
    assert widget.canvas.zoom_factor <= initial_zoom + 0.05
    widget.canvas.reset_zoom()
    assert widget.canvas.zoom_factor == 1.0
    assert widget.canvas.pan_offset == QPointF(0, 0)

    # Test toggles
    assert widget.canvas.show_trainers is True
    widget.btn_trainers.click()
    assert widget.canvas.show_trainers is False
    widget.btn_trainers.click()
    assert widget.canvas.show_trainers is True


def test_wasd_and_arrow_keys_navigation(qapp):
    from PySide6.QtGui import QKeyEvent

    widget = RegionalMapWidget()
    canvas = widget.canvas
    canvas.selected_node = "Oldale Town"

    # W (Up)
    event_w = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_W, Qt.NoModifier)
    canvas.keyPressEvent(event_w)
    assert canvas.selected_node is not None

    # S (Down)
    event_s = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_S, Qt.NoModifier)
    canvas.keyPressEvent(event_s)
    assert canvas.selected_node is not None

    # A (Left)
    event_a = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_A, Qt.NoModifier)
    canvas.keyPressEvent(event_a)
    assert canvas.selected_node is not None

    # D (Right)
    event_d = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_D, Qt.NoModifier)
    canvas.keyPressEvent(event_d)
    assert canvas.selected_node is not None


def test_button_a_and_b(qapp):
    from PySide6.QtGui import QKeyEvent

    widget = RegionalMapWidget()
    canvas = widget.canvas
    canvas.selected_node = "Littleroot Town"

    clicked = []
    canvas.node_clicked.connect(lambda n, r: clicked.append((n, r)))

    # Up Arrow is Button A (Select / Confirm)
    event_up = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Up, Qt.NoModifier)
    canvas.keyPressEvent(event_up)
    assert len(clicked) == 1
    assert clicked[0] == ("Littleroot Town", REGION_HOENN)

    # Down Arrow is Button B (Cancel / Back)
    event_down = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Down, Qt.NoModifier)
    canvas.keyPressEvent(event_down)
    # Shouldn't trigger node_clicked
    assert len(clicked) == 1


def test_shoulders_l_r_and_start(qapp):
    from PySide6.QtGui import QKeyEvent

    widget = RegionalMapWidget()
    canvas = widget.canvas
    canvas.selected_node = "Littleroot Town"

    # Right Arrow is Button R (Next route)
    event_r = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Right, Qt.NoModifier)
    canvas.keyPressEvent(event_r)
    first_jump = canvas.selected_node
    assert first_jump != "Littleroot Town"

    # Left Arrow is Button L (Prev route)
    event_l = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Left, Qt.NoModifier)
    canvas.keyPressEvent(event_l)
    assert canvas.selected_node == "Littleroot Town"

    # Space is Button START
    start_called = []
    canvas.start_menu_requested.connect(lambda: start_called.append(True))
    event_space = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Space, Qt.NoModifier)
    canvas.keyPressEvent(event_space)
    assert len(start_called) == 1


def test_retro_filter_popup_toggle_and_select(qapp):
    from PySide6.QtGui import QKeyEvent

    widget = RegionalMapWidget()
    canvas = widget.canvas
    widget.set_retro_mode(True)
    assert canvas.is_retro is True

    # Press F to toggle popup
    event_f = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_F, Qt.NoModifier)
    canvas.keyPressEvent(event_f)
    assert canvas.filter_popup_open is True

    # Press S (Down) in popup
    event_s = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_S, Qt.NoModifier)
    canvas.keyPressEvent(event_s)
    assert canvas.filter_popup_idx == 1  # "incomplete" / "MISSING ENCOUNTERS"

    # Press Up Arrow (Button A) to confirm selection
    event_a = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Up, Qt.NoModifier)
    canvas.keyPressEvent(event_a)
    assert canvas.filter_popup_open is False
    assert canvas.filter_mode == "incomplete"

    # Test legendary filter
    canvas.set_filter_mode("legendary")
    assert canvas.filter_mode == "legendary"
    assert canvas._matches_filter("Sky Pillar") is True


def test_gba_start_menu_widget_controls(qapp):
    from PySide6.QtGui import QKeyEvent
    from gba_start_menu_widget import GbaStartMenuOverlay

    menu = GbaStartMenuOverlay()
    menu.show_menu()
    assert menu.isVisible()
    assert menu.selected_index == 0

    # S moves down
    event_s = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_S, Qt.NoModifier)
    menu.keyPressEvent(event_s)
    assert menu.selected_index == 1

    # W moves up
    event_w = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_W, Qt.NoModifier)
    menu.keyPressEvent(event_w)
    assert menu.selected_index == 0

    # Right Arrow (R) jumps to bottom
    event_r = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Right, Qt.NoModifier)
    menu.keyPressEvent(event_r)
    assert menu.selected_index == len(menu.menu_items) - 1

    # Left Arrow (L) jumps to top
    event_l = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Left, Qt.NoModifier)
    menu.keyPressEvent(event_l)
    assert menu.selected_index == 0

    # Up Arrow (Button A) selects active item
    actions = []
    menu.action_triggered.connect(lambda act: actions.append(act))
    event_up = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Up, Qt.NoModifier)
    menu.keyPressEvent(event_up)
    assert len(actions) == 1
    assert actions[0] == menu.menu_items[0]["id"]
    assert not menu.isVisible()

    # Reopen and test Down Arrow (Button B) closes menu
    menu.show_menu()
    assert menu.isVisible()
    event_down = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Down, Qt.NoModifier)
    menu.keyPressEvent(event_down)
    assert not menu.isVisible()


def test_sfx_non_blocking_performance():
    from regional_map_widget import play_sfx

    # Rapid fire calls must not block or hang
    for _ in range(20):
        play_sfx("menu_move.wav")
        play_sfx("menu_select.wav")
        play_sfx("menu_cancel.wav")

