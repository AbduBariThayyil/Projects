"""
Macro recording, editing, and playback engine for Ant Esports GM320.
Supports millisecond precision event recording, onboard EEPROM byte compilation,
and software playback testing.
"""

import time
import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from PySide6.QtCore import QObject, Signal, QThread
from ant_gm320.core.usb_hid_keys import HID_KEY_MAP, HID_CODE_TO_NAME


@dataclass
class MacroEvent:
    event_type: str  # "key_down", "key_up", "mouse_click", "delay"
    key: str = ""    # Key name e.g. "a", "ctrl", "f1"
    button: str = "" # "left", "right", "middle"
    delay_ms: int = 20

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MacroEvent":
        return cls(**data)

    def display_text(self) -> str:
        if self.event_type == "key_down":
            return f"Key Down [{self.key.upper()}]"
        elif self.event_type == "key_up":
            return f"Key Up [{self.key.upper()}]"
        elif self.event_type == "mouse_click":
            return f"Mouse Click [{self.button.title()}]"
        elif self.event_type == "delay":
            return f"Delay: {self.delay_ms} ms"
        return "Unknown Event"


@dataclass
class Macro:
    name: str
    events: List[MacroEvent] = field(default_factory=list)
    cycle_mode: str = "until_released"  # "until_released", "until_clicked_again", "repeat_count"
    repeat_count: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "cycle_mode": self.cycle_mode,
            "repeat_count": self.repeat_count,
            "events": [e.to_dict() for e in self.events],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Macro":
        events = [MacroEvent.from_dict(e) for e in data.get("events", [])]
        return cls(
            name=data.get("name", "New Macro"),
            events=events,
            cycle_mode=data.get("cycle_mode", "until_released"),
            repeat_count=data.get("repeat_count", 1),
        )

    def to_hardware_bytecode(self) -> bytes:
        """
        Compiles the macro into Instant Microelectronics 8-byte macro frames.
        Frame layout:
          [action_type, 0x00, 0xFF, delay_lo, delay_hi, 0x00, hid_scancode, 0x00]
        """
        bytecode = bytearray()
        for e in self.events:
            if e.event_type == "delay":
                d = min(65535, max(1, e.delay_ms))
                bytecode.extend([0x03, 0x00, 0xFF, d & 0xFF, (d >> 8) & 0xFF, 0x00, 0x00, 0x00])
            elif e.event_type == "key_down":
                sc = HID_KEY_MAP.get(e.key.lower(), 0x04)
                bytecode.extend([0x01, 0x00, 0xFF, 0x14, 0x00, 0x00, sc, 0x00])
            elif e.event_type == "key_up":
                sc = HID_KEY_MAP.get(e.key.lower(), 0x04)
                bytecode.extend([0x00, 0x00, 0xFF, 0x14, 0x00, 0x00, sc, 0x00])
            elif e.event_type == "mouse_click":
                # Mouse click: down, delay 20ms, up
                btn_code = 0x01 if e.button == "left" else (0x02 if e.button == "right" else 0x04)
                bytecode.extend([0x02, btn_code, 0xFF, 0x14, 0x00, 0x00, 0x00, 0x00])
        return bytes(bytecode)


class MacroRecorder(QObject):
    """
    High-precision event recorder.
    Emits events as they are recorded with millisecond timestamps.
    """
    event_recorded = Signal(MacroEvent)
    state_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_recording = False
        self._last_timestamp = 0.0
        self._events: List[MacroEvent] = []

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def start_recording(self):
        self._is_recording = True
        self._last_timestamp = time.perf_counter()
        self._events.clear()
        self.state_changed.emit(True)

    def stop_recording(self) -> List[MacroEvent]:
        self._is_recording = False
        self.state_changed.emit(False)
        return list(self._events)

    def record_key_event(self, event_type: str, key_name: str):
        if not self._is_recording:
            return

        now = time.perf_counter()
        delta_ms = int((now - self._last_timestamp) * 1000)
        self._last_timestamp = now

        # Add delay event if meaningful gap
        if delta_ms > 5 and len(self._events) > 0:
            delay_event = MacroEvent(event_type="delay", delay_ms=delta_ms)
            self._events.append(delay_event)
            self.event_recorded.emit(delay_event)

        action_event = MacroEvent(event_type=event_type, key=key_name.lower())
        self._events.append(action_event)
        self.event_recorded.emit(action_event)

    def record_mouse_click(self, button_name: str):
        if not self._is_recording:
            return

        now = time.perf_counter()
        delta_ms = int((now - self._last_timestamp) * 1000)
        self._last_timestamp = now

        if delta_ms > 5 and len(self._events) > 0:
            delay_event = MacroEvent(event_type="delay", delay_ms=delta_ms)
            self._events.append(delay_event)
            self.event_recorded.emit(delay_event)

        action_event = MacroEvent(event_type="mouse_click", button=button_name.lower())
        self._events.append(action_event)
        self.event_recorded.emit(action_event)
