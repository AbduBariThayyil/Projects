"""
Protocol implementation for Ant Esports GM320 Gaming Mouse (Instant USB Gaming Mouse).
USB VID: 0x30fa, PID: 0x1440.

Handles EEPROM binary layout, block packet encoding, real-time LED streaming,
and hardware opcode generation.
"""

from typing import List, Dict, Any, Tuple
import struct

# Report ID and Opcodes
REPORT_ID = 0x07
CMD_EEPROM_PREFIX = 0x18
OPCODE_WRITE_BYTE = 0x03
OPCODE_FLUSH_BLOCK = 0x09
OPCODE_BLOCK_END = 0x00
OPCODE_FLASH_COMMIT = 0x10
OPCODE_LIVE_LED = 0x14
OPCODE_AUDIO_MODE = 0x13
OPCODE_RESTORE = 0x20

EEPROM_SIZE = 681

# Button Mapping Codes
BUTTON_FUNCTIONS: Dict[str, int] = {
    "left_click": 0x21,
    "right_click": 0x22,
    "middle_click": 0x23,
    "forward": 0x24,
    "backward": 0x25,
    "dpi_loop": 0x26,
    "dpi_up": 0x27,
    "dpi_down": 0x28,
    "led_loop": 0x29,
    "volume_up": 0x2A,
    "volume_down": 0x2B,
    "prev_track": 0x2C,
    "next_track": 0x2D,
    "mute": 0x2E,
    "play_pause": 0x2F,
    "media_player": 0x30,
    "media_stop": 0x31,
    "mail": 0x32,
    "calculator": 0x33,
    "browser": 0x34,
    "rapid_fire": 0x35,
    "double_click": 0x36,
    "my_computer": 0x37,
    "boss_key": 0x38,
    "macro": 0x2F,
    "disabled": 0x00,
}

BUTTON_NAMES: Dict[int, str] = {
    0x21: "Left Click",
    0x22: "Right Click",
    0x23: "Middle Click",
    0x24: "Forward",
    0x25: "Backward",
    0x26: "DPI Loop",
    0x27: "DPI +",
    0x28: "DPI -",
    0x29: "LED Loop",
    0x35: "Rapid Fire",
    0x34: "Browser (Home)",
    0x33: "Calculator",
    0x32: "E-Mail",
    0x30: "Media Player",
    0x2F: "Play / Pause",
    0x2C: "Previous Track",
    0x2D: "Next Track",
    0x2A: "Volume +",
    0x2B: "Volume -",
    0x2E: "Mute Audio",
    0x38: "Show Desktop (Boss)",
    0x36: "Double Click",
    0x37: "My Computer",
    0x00: "Disabled",
}

# LED Lighting Modes (matching Instant Microelectronics OEM table)
LED_MODES: Dict[str, int] = {
    "ambilight": 8,
    "neon": 7,
    "reaction": 13,
    "cycle_breath": 2,
    "static": 3,
    "flowing_water": 4,
    "mono_water": 5,
    "comet_streak": 6,
    "star_trek": 10,
    "ripple": 11,
    "flicker": 9,
    "enraptured": 12,
    "single_breath": 15,
    "dpi_breath": 1,
    "cycle_color": 16,
    "off": 14,
}

LED_MODE_NAMES: Dict[int, str] = {
    8: "Ambilight (Rainbow Wave)",
    7: "Neon Flow",
    13: "Button Response",
    2: "Cycle Breathing",
    3: "Light On (Static Color)",
    4: "Flowing Water (Comet Tail)",
    5: "Mono Water Effect",
    6: "Comet Streak",
    10: "Star Trek",
    11: "Ripple",
    9: "Flicker (Strobe)",
    12: "Enraptured",
    15: "Single Color Breath",
    1: "DPI Breathing",
    16: "Cycle Color",
    14: "LED Off",
}

# Button Response Hardware Reaction Effects
REACTION_TYPES: Dict[int, str] = {
    0: "Ripple",
    1: "Comet Streak",
    2: "Fast Pulse / Flash",
    3: "Neon Burst",
    4: "Single Breath",
    5: "Flowing Wave",
    6: "Star Trek",
}

# Polling Rates (Hz -> Hardware Register Value)
POLLING_RATE_MAP = {
    125: 0,
    250: 1,
    500: 2,
    1000: 3,
}

POLLING_RATE_REV = {
    0: 125,
    1: 250,
    2: 500,
    3: 1000,
}


def build_eeprom_image(config: Dict[str, Any], initial_base: bytes = None) -> bytearray:
    """
    Builds the complete 681-byte EEPROM image from configuration dictionary.
    Preserves existing factory calibration/macro areas if initial_base is provided.
    """
    buf = bytearray(initial_base if initial_base and len(initial_base) >= EEPROM_SIZE else EEPROM_SIZE)
    if len(buf) < EEPROM_SIZE:
        buf.extend(b"\x00" * (EEPROM_SIZE - len(buf)))

    # 1. Header flag
    buf[0x0001] = 0x03

    # 2. Button mappings (K1..K8)
    buttons = config.get("buttons", {})
    # Button physical indices:
    # 0x0008: K1 (Left)
    # 0x0009: K2 (Right)
    # 0x000A: K3 (Middle)
    # 0x000B: K7 (Forward)
    # 0x000C: K8 (Backward)
    # 0x000D: K6 (Rapid Fire)
    # 0x000E: reserved (0x00)
    # 0x000F: K4 (DPI Loop)
    # 0x0010: K5 (LED Loop)
    buf[0x0008] = buttons.get("button1", 0x21)
    buf[0x0009] = buttons.get("button2", 0x22)
    buf[0x000A] = buttons.get("button3", 0x23)
    buf[0x000B] = buttons.get("button7", 0x24)
    buf[0x000C] = buttons.get("button8", 0x25)
    buf[0x000D] = buttons.get("button6", 0x35)
    buf[0x000E] = 0x00
    buf[0x000F] = buttons.get("button4", 0x26)
    buf[0x0010] = buttons.get("button5", 0x29)

    # 3. DPI Stages
    dpi_config = config.get("dpi", {})
    stages = dpi_config.get("stages", [
        {"dpi": 1400, "enabled": True, "color": (255, 255, 0)},
        {"dpi": 1800, "enabled": True, "color": (0, 0, 255)},
        {"dpi": 3200, "enabled": True, "color": (255, 0, 255)},
        {"dpi": 4000, "enabled": True, "color": (0, 255, 0)},
        {"dpi": 5600, "enabled": True, "color": (255, 0, 0)},
        {"dpi": 8000, "enabled": True, "color": (0, 255, 255)},
    ])
    active_stage = dpi_config.get("active_stage", 0)

    # Active level index
    buf[0x0018] = min(active_stage, 5)

    # Enabled bitmask
    mask = 0
    for idx, s in enumerate(stages[:6]):
        if s.get("enabled", True):
            mask |= (1 << idx)
    buf[0x0019] = mask if mask > 0 else 0x01

    # Stage DPI values & RGB colors
    # Hardware DPI step values
    for idx, s in enumerate(stages[:6]):
        dpi_val = s.get("dpi", 1200)
        # Register step mapping: approx dpi / 100 or mapped step
        step = max(1, min(128, int(dpi_val / 100)))
        buf[0x001A + idx] = step

        # RGB Colors: 0x0022..0x0033 (3 bytes per stage)
        r, g, b = s.get("color", (255, 255, 255))
        c_addr = 0x0022 + (idx * 3)
        buf[c_addr] = min(255, max(0, r))
        buf[c_addr + 1] = min(255, max(0, g))
        buf[c_addr + 2] = min(255, max(0, b))

    # 4. LED Configuration
    led = config.get("lighting", {})
    led_mode = led.get("mode", 8)  # default Ambilight
    buf[0x003D] = led_mode

    speed = max(1, min(10, led.get("speed", 5)))
    buf[0x003A] = speed

    # Flags: Direction & Symmetry
    # bit 0 = direction (0=cw, 1=ccw), bit 1 = symmetry
    direction = 1 if led.get("direction", "cw") == "ccw" else 0
    symmetry = 1 if led.get("symmetry", False) else 0
    flags = (symmetry << 1) | direction
    buf[0x003E] = flags

    # Brightness (0x003C or 0x003F)
    brightness = max(1, min(5, led.get("brightness", 4)))
    buf[0x003C] = brightness

    # 4b. Custom Color Combinations & Palette Mask
    colors = led.get("colors", [])
    enables = led.get("color_enables", [True] * 7)
    cyc_mask = 0
    for idx, en in enumerate(enables[:7]):
        if en:
            cyc_mask |= (1 << idx)
    buf[0x0043] = cyc_mask if cyc_mask > 0 else 0x7F

    # 5. Performance Settings
    perf = config.get("performance", {})
    polling = perf.get("polling_rate", 500)
    buf[0x0068] = POLLING_RATE_MAP.get(polling, 2)

    sensitivity = max(1, min(11, perf.get("sensitivity", 6)))
    buf[0x0069] = sensitivity

    scroll_speed = max(1, min(11, perf.get("scroll_speed", 4)))
    buf[0x006A] = scroll_speed

    # 6. Profile Slots (Office 0x40, Game I 0x50, Game II 0x60, Media 0x70)
    # Replicate active button mappings to current slot
    for slot_base in [0x0040, 0x0050, 0x0060]:
        buf[slot_base + 4] = buf[0x0008]
        buf[slot_base + 5] = buf[0x0009]
        buf[slot_base + 6] = buf[0x000A]
        buf[slot_base + 7] = buf[0x000B]
        buf[slot_base + 8] = buf[0x000C]
        buf[slot_base + 9] = buf[0x000D]
        buf[slot_base + 11] = buf[0x000F]
        buf[slot_base + 12] = buf[0x0010]

    # 7. Hardware Footer & Button Response Hardware Table
    # Preserves OEM factory response table at 0x006E..0x007F
    buf[0x006E] = 0x00
    buf[0x006F] = 0x04
    default_70 = [0x08, 0x04, 0x10, 0x04, 0x18, 0x04, 0x01, 0x71]
    default_78 = [0xAA, 0x18, 0x04, 0x20, 0x04, 0x20, 0x01, 0x00]
    for idx, v in enumerate(default_70):
        buf[0x0070 + idx] = v
    for idx, v in enumerate(default_78):
        buf[0x0078 + idx] = v

    return buf


def format_eeprom_write_packets(buffer: bytearray) -> List[bytes]:
    """
    Generates the complete sequence of 8-byte HID feature reports
    to burn the given EEPROM image into mouse hardware.
    Matches the Instant Microelectronics hardware protocol byte-for-byte:
      - Block 0x0001 (1 byte write, flush, end)
      - Blocks 0x0008..0x0068 (8 bytes each, flush, end)
      - Probe sequence at 0x0076 (4 packets)
      - First pass 0x0070 and 0x0078 (8 bytes each, flush, end)
      - Macro blocks 0x00A0..0x02C8 (70 blocks * 8 bytes)
      - Footer block 0x006E (exactly 2 bytes, last_byte=0x01, flush, end)
      - Footer blocks 0x0070 and 0x0078 (hardware response table, 8 bytes each)
      - Flash commit opcode 0x10 and end opcode 0x00.
    """
    packets = []

    # 1. Block 0x0001 (1 byte write)
    data_byte = buffer[0x0001] if len(buffer) > 1 else 0x03
    packets.append(bytes([REPORT_ID, CMD_EEPROM_PREFIX, OPCODE_WRITE_BYTE, 0x00, 0x01, 0x00, data_byte, 0x00]))
    packets.append(bytes([REPORT_ID, CMD_EEPROM_PREFIX, OPCODE_FLUSH_BLOCK, 0x00, 0x01, 0x00, 0x00, 0x00]))
    packets.append(bytes([REPORT_ID, CMD_EEPROM_PREFIX, OPCODE_BLOCK_END, 0x00, 0x01, 0x00, 0x00, 0x00]))

    # 2. Main data blocks: 0x0008..0x0068
    main_blocks = [
        0x0008, 0x0010, 0x0018, 0x0020, 0x0028, 0x0030, 0x0038,
        0x0040, 0x0048, 0x0050, 0x0058, 0x0060, 0x0068
    ]
    for addr in main_blocks:
        addr_lo = addr & 0xFF
        addr_hi = (addr >> 8) & 0xFF
        for byte_idx in range(8):
            full_addr = addr + byte_idx
            b = buffer[full_addr] if full_addr < len(buffer) else 0x00
            packets.append(bytes([REPORT_ID, CMD_EEPROM_PREFIX, OPCODE_WRITE_BYTE, byte_idx, addr_lo, addr_hi, b, 0x07]))
        packets.append(bytes([REPORT_ID, CMD_EEPROM_PREFIX, OPCODE_FLUSH_BLOCK, 0x00, addr_lo, addr_hi, 0x00, 0x07]))
        packets.append(bytes([REPORT_ID, CMD_EEPROM_PREFIX, OPCODE_BLOCK_END, 0x00, addr_lo, addr_hi, 0x00, 0x00]))

    # 3. OEM probe sequence at 0x0076 (4 packets)
    packets.append(bytes([REPORT_ID, CMD_EEPROM_PREFIX, 0x03, 0x00, 0x76, 0x00, 0x00, 0x00]))
    packets.append(bytes([REPORT_ID, CMD_EEPROM_PREFIX, 0x00, 0x00, 0x76, 0x00, 0x00, 0x00]))
    packets.append(bytes([REPORT_ID, CMD_EEPROM_PREFIX, 0x05, 0x00, 0x76, 0x00, 0x00, 0x00]))
    packets.append(bytes([REPORT_ID, CMD_EEPROM_PREFIX, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]))

    # 4. First pass of 0x0070 and 0x0078
    for addr in [0x0070, 0x0078]:
        addr_lo = addr & 0xFF
        addr_hi = (addr >> 8) & 0xFF
        for byte_idx in range(8):
            packets.append(bytes([REPORT_ID, CMD_EEPROM_PREFIX, OPCODE_WRITE_BYTE, byte_idx, addr_lo, addr_hi, 0x00, 0x07]))
        packets.append(bytes([REPORT_ID, CMD_EEPROM_PREFIX, OPCODE_FLUSH_BLOCK, 0x00, addr_lo, addr_hi, 0x00, 0x07]))
        packets.append(bytes([REPORT_ID, CMD_EEPROM_PREFIX, OPCODE_BLOCK_END, 0x00, addr_lo, addr_hi, 0x00, 0x00]))

    # 5. Macro blocks 0x00A0..0x02C8 (70 blocks)
    for m_addr in range(0x00A0, 0x02D0, 8):
        m_lo = m_addr & 0xFF
        m_hi = (m_addr >> 8) & 0xFF
        for byte_idx in range(8):
            full_addr = m_addr + byte_idx
            b = buffer[full_addr] if full_addr < len(buffer) else 0x00
            packets.append(bytes([REPORT_ID, CMD_EEPROM_PREFIX, OPCODE_WRITE_BYTE, byte_idx, m_lo, m_hi, b, 0x07]))
        packets.append(bytes([REPORT_ID, CMD_EEPROM_PREFIX, OPCODE_FLUSH_BLOCK, 0x00, m_lo, m_hi, 0x00, 0x07]))
        packets.append(bytes([REPORT_ID, CMD_EEPROM_PREFIX, OPCODE_BLOCK_END, 0x00, m_lo, m_hi, 0x00, 0x00]))

    # 6. Footer block 0x006E (exactly 2 bytes, last_byte = 0x01)
    b0 = buffer[0x006E] if len(buffer) > 0x006E else 0x00
    b1 = buffer[0x006F] if len(buffer) > 0x006F else 0x04
    packets.append(bytes([REPORT_ID, CMD_EEPROM_PREFIX, OPCODE_WRITE_BYTE, 0x00, 0x6E, 0x00, b0, 0x01]))
    packets.append(bytes([REPORT_ID, CMD_EEPROM_PREFIX, OPCODE_WRITE_BYTE, 0x01, 0x6E, 0x00, b1, 0x01]))
    packets.append(bytes([REPORT_ID, CMD_EEPROM_PREFIX, OPCODE_FLUSH_BLOCK, 0x00, 0x6E, 0x00, 0x00, 0x01]))
    packets.append(bytes([REPORT_ID, CMD_EEPROM_PREFIX, OPCODE_BLOCK_END, 0x00, 0x6E, 0x00, 0x00, 0x00]))

    # 7. Footer blocks 0x0070 and 0x0078 (hardware response table)
    for addr in [0x0070, 0x0078]:
        addr_lo = addr & 0xFF
        addr_hi = (addr >> 8) & 0xFF
        for byte_idx in range(8):
            full_addr = addr + byte_idx
            b = buffer[full_addr] if full_addr < len(buffer) else 0x00
            packets.append(bytes([REPORT_ID, CMD_EEPROM_PREFIX, OPCODE_WRITE_BYTE, byte_idx, addr_lo, addr_hi, b, 0x07]))
        packets.append(bytes([REPORT_ID, CMD_EEPROM_PREFIX, OPCODE_FLUSH_BLOCK, 0x00, addr_lo, addr_hi, 0x00, 0x07]))
        packets.append(bytes([REPORT_ID, CMD_EEPROM_PREFIX, OPCODE_BLOCK_END, 0x00, addr_lo, addr_hi, 0x00, 0x00]))

    # 8. Flash Commit & Commit End
    packets.append(bytes([REPORT_ID, CMD_EEPROM_PREFIX, OPCODE_FLASH_COMMIT, 0x00, 0x00, 0x00, 0x00, 0x00]))
    packets.append(bytes([REPORT_ID, CMD_EEPROM_PREFIX, OPCODE_BLOCK_END, 0x00, 0x00, 0x00, 0x00, 0x00]))

    return packets

    return packets


def format_live_led_packet(zone: int, r: int, g: int, b: int) -> bytes:
    """
    Constructs a live direct LED streaming packet (Opcode 0x14).
    Color nibbles are scaled to 0..15.
    """
    r_val = min(31, max(0, int(r * 31 / 255)))
    g_val = min(15, max(0, int(g * 15 / 255)))
    b_val = min(15, max(0, int(b * 15 / 255)))

    byte2 = (zone << 5) | (r_val & 0x1F)
    byte3 = (g_val << 4) | (b_val & 0x0F)

    return bytes([REPORT_ID, OPCODE_LIVE_LED, byte2, byte3, 0x00, 0x00, 0x00, 0x07])


def format_audio_mode_packet() -> bytes:
    """
    Constructs the audio mode activation packet (Opcode 0x13).
    """
    return bytes([REPORT_ID, OPCODE_AUDIO_MODE, 0xFF, 0xE1, 0x10, 0x00, 0x03, 0xFF])


def format_restore_mode_packet() -> bytes:
    """
    Constructs the hardware mode restore packet (Opcode 0x20).
    Exits live LED streaming / EEPROM programming state and restores autonomous lighting.
    """
    return bytes([REPORT_ID, OPCODE_RESTORE, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
