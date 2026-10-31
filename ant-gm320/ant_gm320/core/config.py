"""
Configuration and Profile Management for Ant Esports GM320.
Handles persistent storage in ~/.config/ant-gm320/config.json,
profile switching, importing/exporting JSON & OEM INI files (save.ini),
and factory reset defaults.
"""

import os
import json
import configparser
from typing import Dict, Any, List, Tuple, Optional
from ant_gm320.core.protocol import BUTTON_FUNCTIONS, LED_MODES

CONFIG_DIR = os.path.expanduser("~/.config/ant-gm320")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

# DPI Step Value Map from OEM firmware
OEM_DPI_TABLE = {
    0: 200, 1: 400, 2: 600, 3: 800, 4: 1000, 5: 1200,
    6: 1400, 7: 1600, 8: 1800, 9: 2000, 10: 2400, 11: 3200,
    12: 4000, 13: 4800, 14: 5600, 15: 6400, 16: 7200, 17: 8000, 18: 12800
}

# OEM Function code to our standard bytecode mapping
OEM_BUTTON_MAP = {
    1: 0x21,   # Left Click
    2: 0x23,   # Middle Click
    3: 0x22,   # Right Click
    4: 0x25,   # Backward
    5: 0x24,   # Forward
    6: 0x26,   # DPI Loop
    12: 0x38,  # Show Desktop (Boss Key)
    13: 0x36,  # Double Click
    14: 0x35,  # Rapid Fire
    15: 0x29,  # LED Loop
    16: 0x27,  # DPI +
    17: 0x28,  # DPI -
    23: 0x34,  # Browser (WWW Home)
    24: 0x30,  # Media Player
    25: 0x32,  # Mail
    26: 0x2A,  # Volume Up
    27: 0x2B,  # Volume Down
    28: 0x2C,  # Previous Track
    29: 0x2D,  # Next Track
    30: 0x2E,  # Mute Audio
    31: 0x2F,  # Play / Pause
    32: 0x33,  # Calculator
    35: 0x37,  # My Computer
    0: 0x00,   # Disabled
}


def get_default_profiles() -> Dict[str, Any]:
    """Generates OEM default profiles: Office, Game I, Game II, Media."""
    return {
        "Office": {
            "buttons": {
                "button1": 0x21, "button2": 0x22, "button3": 0x23,
                "button4": 0x26, "button5": 0x29, "button6": 0x35,
                "button7": 0x24, "button8": 0x25,
            },
            "dpi": {
                "active_stage": 1,
                "stages": [
                    {"dpi": 1400, "enabled": True, "color": [0, 0, 255]},
                    {"dpi": 1800, "enabled": True, "color": [255, 255, 0]},
                    {"dpi": 3200, "enabled": True, "color": [0, 255, 0]},
                    {"dpi": 4000, "enabled": True, "color": [255, 0, 187]},
                    {"dpi": 5600, "enabled": True, "color": [0, 255, 255]},
                    {"dpi": 8000, "enabled": True, "color": [255, 255, 0]},
                ]
            },
            "lighting": {
                "mode": 7,  # Neon
                "speed": 3,
                "brightness": 4,
                "direction": "ccw",
                "symmetry": True,
                "colors": [
                    [0, 17, 255], [255, 136, 0], [0, 255, 136],
                    [255, 0, 187], [0, 255, 255], [255, 0, 0], [136, 255, 0]
                ],
                "color_enables": [True, True, True, True, True, True, True]
            },
            "performance": {
                "polling_rate": 500,
                "sensitivity": 6,
                "scroll_speed": 4,
                "double_click_speed": 140,
                "fire_delay": 141
            }
        },
        "Game I": {
            "buttons": {
                "button1": 0x21, "button2": 0x22, "button3": 0x23,
                "button4": 0x26, "button5": 0x29, "button6": 0x35,
                "button7": 0x24, "button8": 0x25,
            },
            "dpi": {
                "active_stage": 1,
                "stages": [
                    {"dpi": 400, "enabled": True, "color": [255, 0, 0]},
                    {"dpi": 800, "enabled": True, "color": [0, 150, 255]},
                    {"dpi": 1200, "enabled": True, "color": [255, 255, 0]},
                    {"dpi": 1600, "enabled": True, "color": [0, 255, 0]},
                    {"dpi": 3200, "enabled": True, "color": [255, 0, 255]},
                    {"dpi": 6400, "enabled": True, "color": [0, 255, 255]},
                ]
            },
            "lighting": {
                "mode": 7,
                "speed": 7,
                "brightness": 5,
                "direction": "cw",
                "symmetry": True,
                "colors": [
                    [255, 0, 80], [0, 255, 255], [255, 200, 0],
                    [150, 0, 255], [0, 255, 100], [255, 50, 0], [0, 100, 255]
                ],
                "color_enables": [True, True, True, True, True, True, True]
            },
            "performance": {
                "polling_rate": 1000,
                "sensitivity": 6,
                "scroll_speed": 4,
                "double_click_speed": 130,
                "fire_delay": 40
            }
        },
        "Game II": {
            "buttons": {
                "button1": 0x21, "button2": 0x22, "button3": 0x23,
                "button4": 0x26, "button5": 0x29, "button6": 0x35,
                "button7": 0x24, "button8": 0x25,
            },
            "dpi": {
                "active_stage": 2,
                "stages": [
                    {"dpi": 800, "enabled": True, "color": [0, 255, 255]},
                    {"dpi": 1600, "enabled": True, "color": [255, 0, 150]},
                    {"dpi": 2400, "enabled": True, "color": [255, 255, 0]},
                    {"dpi": 3200, "enabled": True, "color": [0, 255, 50]},
                    {"dpi": 6400, "enabled": True, "color": [255, 50, 0]},
                    {"dpi": 12800, "enabled": True, "color": [180, 0, 255]},
                ]
            },
            "lighting": {
                "mode": 1,
                "speed": 6,
                "brightness": 4,
                "direction": "cw",
                "symmetry": False,
                "colors": [
                    [0, 240, 255], [255, 255, 0], [255, 0, 0],
                    [255, 100, 180], [0, 0, 255], [0, 120, 50], [0, 255, 0]
                ],
                "color_enables": [True, True, True, True, True, True, True]
            },
            "performance": {
                "polling_rate": 1000,
                "sensitivity": 7,
                "scroll_speed": 5,
                "double_click_speed": 130,
                "fire_delay": 35
            }
        },
        "Media": {
            "buttons": {
                "button1": 0x21, "button2": 0x22, "button3": 0x23,
                "button4": 0x26, "button5": 0x29,
                "button6": 0x30,  # Play / Pause
                "button7": 0x33,  # Next Track
                "button8": 0x32,  # Previous Track
            },
            "dpi": {
                "active_stage": 1,
                "stages": [
                    {"dpi": 1000, "enabled": True, "color": [0, 200, 255]},
                    {"dpi": 1600, "enabled": True, "color": [255, 150, 0]},
                    {"dpi": 2400, "enabled": True, "color": [255, 0, 100]},
                    {"dpi": 3200, "enabled": True, "color": [0, 255, 100]},
                ]
            },
            "lighting": {
                "mode": 2,
                "speed": 4,
                "brightness": 3,
                "direction": "cw",
                "symmetry": False,
                "colors": [
                    [0, 200, 255], [255, 255, 0], [255, 0, 0],
                    [255, 100, 180], [0, 0, 255], [0, 120, 50], [0, 255, 0]
                ],
                "color_enables": [True, True, True, True, True, True, True]
            },
            "performance": {
                "polling_rate": 500,
                "sensitivity": 6,
                "scroll_speed": 4,
                "double_click_speed": 140,
                "fire_delay": 50
            }
        }
    }


class ConfigManager:
    def __init__(self):
        self.profiles: Dict[str, Any] = {}
        self.active_profile_name: str = "Office"
        self.macros: List[Dict[str, Any]] = []
        self.load()

    def load(self):
        """Loads configuration from JSON file or auto-imports save.ini if available."""
        user_save_ini = os.path.expanduser("~/Downloads/save.ini")
        if os.path.exists(user_save_ini) and not os.path.exists(CONFIG_FILE):
            ok, _ = self.import_ini(user_save_ini)
            if ok:
                return

        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    self.profiles = data.get("profiles", {})
                    self.active_profile_name = data.get("active_profile", "Office")
                    self.macros = data.get("macros", [])
                    if self.profiles:
                        if self.active_profile_name not in self.profiles:
                            self.active_profile_name = next(iter(self.profiles.keys()), "Office")
                        return
            except Exception:
                pass

        if os.path.exists(user_save_ini):
            ok, _ = self.import_ini(user_save_ini)
            if ok:
                return

        self.profiles = get_default_profiles()
        self.active_profile_name = "Office"
        self.macros = []
        self.save()

    def save(self):
        """Saves current state to JSON."""
        os.makedirs(CONFIG_DIR, exist_ok=True)
        data = {
            "active_profile": self.active_profile_name,
            "profiles": self.profiles,
            "macros": self.macros,
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)

    @property
    def current_profile(self) -> Dict[str, Any]:
        if self.active_profile_name not in self.profiles:
            self.active_profile_name = next(iter(self.profiles.keys()), "Office")
        return self.profiles[self.active_profile_name]

    def set_active_profile(self, name: str):
        if name in self.profiles:
            self.active_profile_name = name
            self.save()

    def add_profile(self, name: str, clone_from: Optional[str] = None):
        if clone_from and clone_from in self.profiles:
            import copy
            self.profiles[name] = copy.deepcopy(self.profiles[clone_from])
        else:
            self.profiles[name] = get_default_profiles()["Office"]
        self.active_profile_name = name
        self.save()

    def delete_profile(self, name: str) -> bool:
        if len(self.profiles) <= 1:
            return False
        if name in self.profiles:
            del self.profiles[name]
            if self.active_profile_name == name:
                self.active_profile_name = next(iter(self.profiles.keys()))
            self.save()
            return True
        return False

    def reset_to_defaults(self):
        self.profiles = get_default_profiles()
        self.active_profile_name = "Office"
        self.save()

    def export_profile(self, file_path: str, profile_name: Optional[str] = None):
        name = profile_name or self.active_profile_name
        data = {
            "version": "1.0",
            "device": "Ant Esports GM320 RGB",
            "profile_name": name,
            "profile_data": self.profiles.get(name, {})
        }
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

    def import_ini(self, ini_path: str) -> Tuple[bool, str]:
        """Imports OEM Windows INI format (e.g. save.ini)."""
        try:
            ini = configparser.ConfigParser(strict=False)
            # Try reading with gbk or utf-8
            try:
                ini.read(ini_path, encoding="gbk")
            except Exception:
                ini.read(ini_path, encoding="utf-8", errors="ignore")

            share = ini["ShareData"] if "ShareData" in ini else {}

            # DPI Stages & Colors from ShareData
            active_dpi_level = int(share.get("DPI_LEVEL", 1))
            default_stages = []
            for i in range(6):
                step_idx = int(share.get(f"DPI_SET{i}", 6))
                dpi_val = OEM_DPI_TABLE.get(step_idx, 1200)
                enabled = int(share.get(f"DPI_SET_EN{i}", 1)) == 1

                # Colors scaled from 0..15 nibble to 0..255
                r = int(share.get(f"DPI{i}_R", 0)) * 17
                g = int(share.get(f"DPI{i}_G", 0)) * 17
                b = int(share.get(f"DPI{i}_B", 0)) * 17
                default_stages.append({
                    "dpi": dpi_val,
                    "enabled": enabled,
                    "color": [r, g, b]
                })

            # Lighting from ShareData
            led_mode = int(share.get("LED_TYPE", 7))
            led_speed = int(share.get("LED_CYC_TIME", share.get("LED_CYCTIME", 3)))
            led_symm = int(share.get("LED_FEATURE_SYMMETRY", 1)) == 1
            led_direc = "ccw" if int(share.get("LED_FEATURE_DIREC", 1)) == 1 else "cw"
            led_bright = int(share.get("LED_BRIGHT", 4))

            # 7-Color Palette & Enables from ShareData
            cyc_mask = int(share.get("CYC_7COL_EN", 127))
            palette_colors = []
            palette_enables = []
            for i in range(7):
                ur = int(share.get(f"LED_USER{i}_R", 0)) * 17
                ug = int(share.get(f"LED_USER{i}_G", 15)) * 17
                ub = int(share.get(f"LED_USER{i}_B", 15)) * 17
                palette_colors.append([ur, ug, ub])
                palette_enables.append(bool(cyc_mask & (1 << i)))

            # Performance from ShareData
            usb_val = int(share.get("USB_SPEED", 2))
            poll_rates = {0: 125, 1: 250, 2: 500, 3: 1000}
            polling_rate = poll_rates.get(usb_val, 500)
            sensitivity = int(share.get("DPI_SPEED", 6))
            scroll_speed = int(share.get("WHEEL_SPEED", 4))
            fire_delay = int(share.get("FIRE_TIME", 141))

            # Profiles in INI: Config0..Config3
            profile_names = ["Office", "Game I", "Game II", "Game III"]
            init_sec = ini["Init"] if "Init" in ini else {}
            if "ConfigName1_EN" in init_sec:
                profile_names[0] = init_sec.get("ConfigName1_EN").strip()
            if "ConfigName2_EN" in init_sec:
                profile_names[1] = init_sec.get("ConfigName2_EN").strip()
            if "ConfigName3_EN" in init_sec:
                profile_names[2] = init_sec.get("ConfigName3_EN").strip()
            if "ConfigName4_EN" in init_sec:
                profile_names[3] = init_sec.get("ConfigName4_EN").strip()

            new_profiles = {}
            for p_idx, p_name in enumerate(profile_names):
                cfg_sec = ini[f"Config{p_idx}"] if f"Config{p_idx}" in ini else {}
                # Button mappings (1-to-1 matching OEM button indices K0..K7)
                buttons = {
                    "button1": OEM_BUTTON_MAP.get(int(cfg_sec.get("K0", 1)), 0x21),
                    "button2": OEM_BUTTON_MAP.get(int(cfg_sec.get("K1", 3)), 0x22),
                    "button3": OEM_BUTTON_MAP.get(int(cfg_sec.get("K2", 2)), 0x23),
                    "button4": OEM_BUTTON_MAP.get(int(cfg_sec.get("K3", 6)), 0x26),
                    "button5": OEM_BUTTON_MAP.get(int(cfg_sec.get("K4", 15)), 0x29),
                    "button6": OEM_BUTTON_MAP.get(int(cfg_sec.get("K5", 14)), 0x35),
                    "button7": OEM_BUTTON_MAP.get(int(cfg_sec.get("K6", 5)), 0x24),
                    "button8": OEM_BUTTON_MAP.get(int(cfg_sec.get("K7", 4)), 0x25),
                }

                # Per-profile DPI overrides if specified in ConfigN
                p_active_dpi = int(cfg_sec.get("DPI_LEVEL", active_dpi_level))
                p_stages = []
                for i in range(6):
                    s_step = int(cfg_sec.get(f"DPI_SET{i}", share.get(f"DPI_SET{i}", 6)))
                    s_dpi = OEM_DPI_TABLE.get(s_step, 1200)
                    s_en = int(cfg_sec.get(f"DPI_SET_EN{i}", share.get(f"DPI_SET_EN{i}", 1))) == 1
                    s_r = int(cfg_sec.get(f"DPI{i}_R", share.get(f"DPI{i}_R", 0))) * 17
                    s_g = int(cfg_sec.get(f"DPI{i}_G", share.get(f"DPI{i}_G", 0))) * 17
                    s_b = int(cfg_sec.get(f"DPI{i}_B", share.get(f"DPI{i}_B", 0))) * 17
                    p_stages.append({
                        "dpi": s_dpi,
                        "enabled": s_en,
                        "color": [s_r, s_g, s_b]
                    })

                # Per-profile Lighting overrides
                p_led_mode = int(cfg_sec.get("LED_TYPE", led_mode))
                p_led_speed = int(cfg_sec.get("LED_CYC_TIME", cfg_sec.get("LED_CYCTIME", led_speed)))
                p_led_bright = int(cfg_sec.get("LED_BRIGHT", led_bright))
                p_led_symm = int(cfg_sec.get("LED_FEATURE_SYMMETRY", 1 if led_symm else 0)) == 1
                p_led_direc = "ccw" if int(cfg_sec.get("LED_FEATURE_DIREC", 1 if led_direc == "ccw" else 0)) == 1 else "cw"

                # Button Response settings from INI: LED_REACT_EN0..7, LED_REACT_TYPE0..7
                r_ens = [int(cfg_sec.get(f"LED_REACT_EN{i}", 1)) == 1 for i in range(8)]
                r_types = [int(cfg_sec.get(f"LED_REACT_TYPE{i}", 0)) for i in range(8)]

                # Per-profile Performance overrides
                p_usb = int(cfg_sec.get("USB_SPEED", usb_val))
                p_poll = poll_rates.get(p_usb, polling_rate)
                p_sens = int(cfg_sec.get("DPI_SPEED", sensitivity))
                p_scroll = int(cfg_sec.get("WHEEL_SPEED", scroll_speed))
                p_fire = int(cfg_sec.get("FIRE_TIME", fire_delay))

                new_profiles[p_name] = {
                    "buttons": buttons,
                    "dpi": {
                        "active_stage": min(p_active_dpi, 5),
                        "stages": list(p_stages),
                    },
                    "lighting": {
                        "mode": p_led_mode,
                        "speed": p_led_speed,
                        "brightness": max(1, p_led_bright),
                        "direction": p_led_direc,
                        "symmetry": p_led_symm,
                        "colors": list(palette_colors),
                        "color_enables": list(palette_enables),
                        "button_response": {
                            "enables": r_ens,
                            "types": r_types,
                        },
                    },
                    "performance": {
                        "polling_rate": p_poll,
                        "sensitivity": p_sens,
                        "scroll_speed": p_scroll,
                        "double_click_speed": 140,
                        "fire_delay": p_fire,
                    }
                }

            self.profiles = new_profiles
            cur_cfg_idx = int(init_sec.get("CurConfig", 0))
            self.active_profile_name = profile_names[min(cur_cfg_idx, len(profile_names) - 1)]
            self.save()
            return True, f"Imported INI config successfully! Loaded {len(self.profiles)} profiles."
        except Exception as e:
            return False, f"Error parsing INI: {e}"

    def import_profile(self, file_path: str) -> Tuple[bool, str]:
        if file_path.lower().endswith(".ini"):
            return self.import_ini(file_path)

        try:
            with open(file_path, "r") as f:
                data = json.load(f)
            name = data.get("profile_name", "Imported Profile")
            profile_data = data.get("profile_data")
            if not profile_data:
                return False, "Invalid profile format."

            # Ensure unique name
            base_name = name
            counter = 1
            while name in self.profiles:
                name = f"{base_name} ({counter})"
                counter += 1

            self.profiles[name] = profile_data
            self.active_profile_name = name
            self.save()
            return True, f"Imported profile '{name}' successfully!"
        except Exception as e:
            return False, f"Failed to import profile: {e}"
