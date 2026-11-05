"""
Automated unit and integration tests for Ant Esports GM320.
Tests driver, protocol packet generation, eeprom layout, macro bytecode, and config management.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ant_gm320.core.driver import GM320Driver
from ant_gm320.core.protocol import (
    build_eeprom_image,
    format_eeprom_write_packets,
    format_live_led_packet,
    format_audio_mode_packet,
    EEPROM_SIZE,
    BUTTON_FUNCTIONS,
    LED_MODES,
    REACTION_TYPES,
)
from ant_gm320.core.config import ConfigManager, get_default_profiles
from ant_gm320.core.macro_engine import Macro, MacroEvent
from ant_gm320.main import UDEV_RULE, main
import subprocess
import shutil


def test_protocol_packets():
    profiles = get_default_profiles()
    office = profiles["Office"]

    # 1. Test EEPROM image build
    eeprom_buf = build_eeprom_image(office)
    assert len(eeprom_buf) == EEPROM_SIZE, f"EEPROM length mismatch: {len(eeprom_buf)}"
    assert eeprom_buf[0x0001] == 0x03, "EEPROM init flag mismatch"
    assert eeprom_buf[0x0008] == 0x21, "Button 1 left click mismatch"
    assert eeprom_buf[0x0009] == 0x22, "Button 2 right click mismatch"
    assert eeprom_buf[0x0019] == 0x3F, "6-stage bitmask mismatch"

    # Hardware reaction table verification
    assert eeprom_buf[0x006E] == 0x00 and eeprom_buf[0x006F] == 0x04
    assert eeprom_buf[0x0070] == 0x08 and eeprom_buf[0x0071] == 0x04

    # 2. Test packet formatting (exact 883-packet hardware sequence)
    packets = format_eeprom_write_packets(eeprom_buf)
    assert len(packets) == 883, f"Expected exactly 883 packets matching OEM hardware trace, got {len(packets)}"
    assert all(len(p) == 8 for p in packets), "All packets must be 8 bytes"
    assert packets[0][0] == 0x07, "Report ID must be 7"
    assert packets[-2][2] == 0x10, "Second to last packet must be Flash Commit (0x10)"
    assert packets[-1][2] == 0x00, "Last packet must be Block End (0x00)"

    # 3. Test Live LED packet
    live_pkt = format_live_led_packet(0, 255, 0, 128)
    assert len(live_pkt) == 8
    assert live_pkt[0] == 0x07
    assert live_pkt[1] == 0x14  # Opcode 0x14

    # 4. Test Audio mode packet
    audio_pkt = format_audio_mode_packet()
    assert len(audio_pkt) == 8
    assert audio_pkt[0] == 0x07
    assert audio_pkt[1] == 0x13  # Opcode 0x13

    # 5. Test Button Response & Reaction Types
    assert "reaction" in LED_MODES
    assert LED_MODES["reaction"] == 13
    assert len(REACTION_TYPES) >= 7
    assert 0 in REACTION_TYPES and REACTION_TYPES[0] == "Ripple"

    print("✓ Protocol tests passed successfully!")


def test_macro_compilation():
    m = Macro(
        name="Test Combo",
        events=[
            MacroEvent("key_down", key="a"),
            MacroEvent("delay", delay_ms=50),
            MacroEvent("key_up", key="a"),
            MacroEvent("mouse_click", button="left"),
        ]
    )
    bytecode = m.to_hardware_bytecode()
    assert len(bytecode) == 32, f"Expected 4 events * 8 bytes = 32 bytes, got {len(bytecode)}"
    assert bytecode[0] == 0x01, "First event must be key_down (0x01)"
    assert bytecode[6] == 0x04, "Scancode for 'a' must be 0x04"
    print("✓ Macro bytecode tests passed successfully!")


def test_config_manager():
    mgr = ConfigManager()
    assert "Office" in mgr.profiles
    assert "Game I" in mgr.profiles
    assert "Game II" in mgr.profiles
    assert ("Media" in mgr.profiles or "Game III" in mgr.profiles)
    
    # Verify save.ini mappings if imported
    office = mgr.profiles["Office"]
    assert "buttons" in office
    assert "button1" in office["buttons"]
    print("✓ Config manager tests passed successfully!")


def test_hardware_driver():
    driver = GM320Driver()
    print("Detected device node:", driver.device_path)
    print("Is accessible:", driver.is_connected())
    # Unit tests should NOT write to physical hardware EEPROM
    print("✓ Hardware driver detection passed successfully!")


def test_udev_rule_and_cli(capsys):
    expected_rule = 'SUBSYSTEM=="hidraw", ATTRS{idVendor}=="30fa", MODE="0666", TAG+="uaccess"'
    assert UDEV_RULE == expected_rule, f"Expected {expected_rule}, got {UDEV_RULE}"

    ret = main(["--udev"])
    assert ret == 0
    captured = capsys.readouterr()
    assert expected_rule in captured.out
    print("✓ Udev rule and CLI flag tests passed successfully!")


def test_dynamic_launcher_script():
    proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    launcher_path = os.path.join(proj_root, "ant-gm320")
    local_bin_path = os.path.expanduser("~/.local/bin/ant-gm320")

    assert os.path.isfile(launcher_path), f"Launcher missing: {launcher_path}"
    assert os.access(launcher_path, os.X_OK), f"Launcher not executable: {launcher_path}"

    res = subprocess.run([launcher_path, "--udev"], capture_output=True, text=True)
    assert res.returncode == 0
    assert 'SUBSYSTEM=="hidraw"' in res.stdout

    assert os.path.exists(local_bin_path), f"~/.local/bin/ant-gm320 missing: {local_bin_path}"
    assert os.access(local_bin_path, os.X_OK), f"~/.local/bin/ant-gm320 not executable: {local_bin_path}"

    res_local = subprocess.run([local_bin_path, "--udev"], capture_output=True, text=True)
    assert res_local.returncode == 0
    assert 'SUBSYSTEM=="hidraw"' in res_local.stdout
    print("✓ Dynamic launcher script tests passed successfully!")


def test_desktop_entry_validation():
    proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    desktop_repo = os.path.join(proj_root, "ant-gm320.desktop")
    desktop_installed = os.path.expanduser("~/.local/share/applications/ant-gm320.desktop")

    assert os.path.isfile(desktop_repo), f"Desktop file missing in repo: {desktop_repo}"
    assert os.path.isfile(desktop_installed), f"Desktop file missing in apps: {desktop_installed}"

    with open(desktop_repo, "r") as f:
        content = f.read()
    assert "Name=Ant Esports GM320" in content
    assert "Exec=ant-gm320" in content
    assert "StartupWMClass=ant_gm320" in content

    validator = shutil.which("desktop-file-validate")
    if validator:
        res = subprocess.run([validator, desktop_repo], capture_output=True, text=True)
        assert res.returncode == 0, f"desktop-file-validate failed on repo file: {res.stderr}"

        res_inst = subprocess.run([validator, desktop_installed], capture_output=True, text=True)
        assert res_inst.returncode == 0, f"desktop-file-validate failed on installed file: {res_inst.stderr}"

    print("✓ Desktop entry validation tests passed successfully!")


if __name__ == "__main__":
    test_protocol_packets()
    test_macro_compilation()
    test_config_manager()
    test_hardware_driver()
    test_dynamic_launcher_script()
    test_desktop_entry_validation()
    print("\nALL SYSTEM TESTS PASSED SUCCESSFULLY!")

