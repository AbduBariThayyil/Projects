"""
Hardware communication driver for Ant Esports GM320 Gaming Mouse.
Handles device detection, hidraw I/O, EEPROM flashing, and live RGB streaming.
"""

import os
import glob
import time
import fcntl
from typing import Optional, List, Dict, Any, Tuple
from ant_gm320.core.protocol import (
    build_eeprom_image,
    format_eeprom_write_packets,
    format_live_led_packet,
    format_audio_mode_packet,
    format_restore_mode_packet,
    REPORT_ID,
)

TARGET_VID = "30FA"
# Instant Microelectronics known PIDs for Ant Esports / Instant mice:
# 0x1440, 0x1e01, 0x1130, 0x1340, 0x1701
KNOWN_PIDS = {"1440", "1E01", "1130", "1340", "1701"}

# Linux HID raw ioctl for setting HID Feature Report (size 8 bytes)
# #define HIDIOCSFEATURE(len) _IOC(_IOC_WRITE|_IOC_READ, 'H', 0x06, len)
HIDIOCSFEATURE_8 = 0xc0084806


class GM320Driver:
    def __init__(self, device_path: Optional[str] = None):
        self._custom_path = device_path
        self._device_path: Optional[str] = None
        self._device_pid: Optional[str] = None
        self._device_name: Optional[str] = None
        self.find_device()

    def find_device(self) -> Optional[str]:
        """
        Locates the GM320 vendor control interface (interface 1 / input1)
        among /sys/class/hidraw entries. Supports dynamic replugging and all Instant PIDs.
        """
        if self._custom_path and os.path.exists(self._custom_path):
            self._device_path = self._custom_path
            return self._device_path

        # Scan sysfs hidraw devices
        matched_nodes = []
        for dev_entry in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
            uevent_file = os.path.join(dev_entry, "device/uevent")
            if os.path.exists(uevent_file):
                try:
                    with open(uevent_file, "r") as f:
                        content = f.read().upper()
                        if TARGET_VID in content:
                            dev_node = "/dev/" + os.path.basename(dev_entry)
                            matched_nodes.append((dev_node, content))
                except (IOError, PermissionError):
                    continue

        if not matched_nodes:
            self._device_path = None
            self._device_pid = None
            return None

        # Prefer interface 1 (input1 or MI_01) which accepts vendor feature reports
        selected_node = None
        for dev_node, content in matched_nodes:
            if "INPUT1" in content or "MI_01" in content:
                selected_node = dev_node
                break

        # Fallback to the second node if available, else first
        if not selected_node:
            if len(matched_nodes) >= 2:
                selected_node = matched_nodes[1][0]
            else:
                selected_node = matched_nodes[0][0]

        self._device_path = selected_node
        return self._device_path

    @property
    def device_path(self) -> Optional[str]:
        # If no path or path no longer exists, scan dynamically
        if not self._device_path or not os.path.exists(self._device_path):
            self.find_device()
        return self._device_path

    def get_status(self) -> Tuple[str, Optional[str]]:
        """
        Returns connection state:
        ('ok', path) - connected and writable
        ('permission_denied', path) - device found but hidraw node lacks write permission
        ('disconnected', None) - mouse not plugged in
        """
        # Always refresh device path to detect replugs
        dev = self.find_device()
        if not dev or not os.path.exists(dev):
            return "disconnected", None
        if os.access(dev, os.W_OK):
            return "ok", dev
        return "permission_denied", dev

    def is_connected(self) -> bool:
        """Checks if the mouse hardware is present and accessible."""
        status, _ = self.get_status()
        return status == "ok"

    def write_report(self, packet: bytes) -> bool:
        """
        Writes an 8-byte HID feature report packet to the mouse hidraw node
        via HIDIOCSFEATURE ioctl.
        """
        dev = self.device_path
        if not dev:
            return False

        try:
            fd = os.open(dev, os.O_RDWR)
            try:
                buf = bytearray(packet)
                fcntl.ioctl(fd, HIDIOCSFEATURE_8, buf)
                return True
            finally:
                os.close(fd)
        except (IOError, PermissionError, OSError):
            return False

    def send_live_led(self, zone: int, r: int, g: int, b: int) -> bool:
        """Sends a live direct RGB streaming packet to mouse."""
        pkt = format_live_led_packet(zone, r, g, b)
        return self.write_report(pkt)

    def set_audio_mode(self) -> bool:
        """Enables the hardware audio streaming mode."""
        pkt = format_audio_mode_packet()
        return self.write_report(pkt)

    def restore_hardware_mode(self) -> bool:
        """
        Restores autonomous mouse lighting and exits host streaming/EEPROM programming mode.
        Sends hardware restore Opcode 0x20 matching OEM trace.
        """
        pkt = format_restore_mode_packet()
        return self.write_report(pkt)

    def apply_configuration(self, config: Dict[str, Any], progress_callback=None) -> Tuple[bool, str]:
        """
        Builds the EEPROM binary image and burns it into the mouse.
        Sends the exact 883-packet feature report sequence via HIDIOCSFEATURE ioctl.
        """
        dev = self.device_path
        if not dev:
            return False, "GM320 mouse not detected. Please ensure USB cable is connected."

        if not os.access(dev, os.W_OK):
            return False, f"Permission denied accessing {dev}. Please check udev rules."

        try:
            eeprom_buffer = build_eeprom_image(config)
            packets = format_eeprom_write_packets(eeprom_buffer)
            total = len(packets)

            fd = os.open(dev, os.O_RDWR)
            try:
                for idx, pkt in enumerate(packets):
                    buf = bytearray(pkt)
                    fcntl.ioctl(fd, HIDIOCSFEATURE_8, buf)
                    time.sleep(0.002)  # Micro-delay between packets to ensure microcontroller write timing
                    if progress_callback and idx % 20 == 0:
                        progress_callback(int((idx / total) * 100))
            finally:
                os.close(fd)

            if progress_callback:
                progress_callback(100)

            # Settle EEPROM write and restore autonomous lighting state
            time.sleep(0.05)
            self.restore_hardware_mode()

            return True, "Configuration successfully saved to mouse EEPROM!"
        except Exception as e:
            return False, f"Error writing to mouse: {e}"
