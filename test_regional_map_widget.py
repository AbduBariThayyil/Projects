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

