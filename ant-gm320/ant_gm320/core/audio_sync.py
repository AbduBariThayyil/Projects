"""
Audio reactive lighting engine for Ant Esports GM320.
Captures desktop audio via PulseAudio/PipeWire simple API without external Python audio dependencies.
Streams real-time dynamic RGB pulses directly to mouse hardware.
"""

import math
import time
import ctypes
from typing import Optional, Tuple
from PySide6.QtCore import QThread, Signal

# PulseAudio C Structures and Prototypes
class pa_sample_spec(ctypes.Structure):
    _fields_ = [
        ("format", ctypes.c_int),
        ("rate", ctypes.c_uint32),
        ("channels", ctypes.c_uint8)
    ]


class AudioSyncWorker(QThread):
    # Signals for UI visualization: bass (0-1), mids (0-1), highs (0-1), peak (0-1)
    metrics_updated = Signal(float, float, float, float)
    beat_detected = Signal()
    status_changed = Signal(bool, str)

    def __init__(self, driver, parent=None):
        super().__init__(parent)
        self.driver = driver
        self._running = False
        self._mode = "bass_pulse"  # bass_pulse, spectrum, neon_flow, strobe
        self._gain = 2.0
        self._color = (0, 229, 255)  # Cyan
        self._secondary_color = (255, 0, 128)  # Pink / Magenta

        # Internal state for audio smoothing & beat tracking
        self._bass_history = []
        self._current_bass = 0.0
        self._current_mids = 0.0
        self._current_highs = 0.0
        self._current_peak = 0.0

        # Load PulseAudio library
        try:
            self._lib = ctypes.cdll.LoadLibrary("libpulse-simple.so.0")
            self._setup_prototypes()
            self._available = True
        except Exception as e:
            self._lib = None
            self._available = False
            self._init_error = str(e)

    def _setup_prototypes(self):
        self._pa_simple_new = self._lib.pa_simple_new
        self._pa_simple_new.restype = ctypes.c_void_p
        self._pa_simple_new.argtypes = [
            ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p,
            ctypes.c_char_p, ctypes.POINTER(pa_sample_spec), ctypes.c_void_p,
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)
        ]

        self._pa_simple_free = self._lib.pa_simple_free
        self._pa_simple_free.restype = None
        self._pa_simple_free.argtypes = [ctypes.c_void_p]

        self._pa_simple_read = self._lib.pa_simple_read
        self._pa_simple_read.restype = ctypes.c_int
        self._pa_simple_read.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_int)
        ]

    @property
    def is_available(self) -> bool:
        return self._available

    def set_mode(self, mode: str):
        self._mode = mode

    def set_gain(self, gain: float):
        self._gain = max(0.5, min(10.0, gain))

    def set_colors(self, primary: Tuple[int, int, int], secondary: Optional[Tuple[int, int, int]] = None):
        self._color = primary
        if secondary:
            self._secondary_color = secondary

    def stop(self):
        self._running = False
        self.wait(2000)

    def run(self):
        if not self._available:
            self.status_changed.emit(False, "PulseAudio/PipeWire simple library not available.")
            return

        # PA_SAMPLE_S16LE = 3, Rate = 44100, Channels = 2 (stereo)
        ss = pa_sample_spec(format=3, rate=44100, channels=2)
        err = ctypes.c_int(0)

        # Open stream recording from default desktop monitor
        stream = self._pa_simple_new(
            None, b"GM320AudioSync", 2, None, b"mouse-lighting-sync",
            ctypes.byref(ss), None, None, ctypes.byref(err)
        )

        if not stream:
            self.status_changed.emit(False, f"Failed to connect to audio monitor (code {err.value})")
            return

        self._running = True
        self.status_changed.emit(True, "Audio reactive lighting active")

        # Put mouse in live lighting mode
        try:
            self.driver.set_audio_mode()
        except Exception:
            pass

        # 1024 16-bit stereo samples = 2048 bytes
        chunk_samples = 1024
        buf = (ctypes.c_int16 * chunk_samples)()
        buf_size = chunk_samples * 2

        last_led_time = time.time()
        color_angle = 0.0

        try:
            while self._running:
                ret = self._pa_simple_read(stream, ctypes.byref(buf), ctypes.c_size_t(buf_size), ctypes.byref(err))
                if ret < 0:
                    time.sleep(0.01)
                    continue

                # Process samples: convert to float normalized (-1.0 to 1.0)
                samples = [s / 32768.0 for s in buf]
                if not samples:
                    continue

                # 1. Peak & RMS Amplitude
                peak = min(1.0, max(abs(s) for s in samples) * self._gain)
                rms = min(1.0, math.sqrt(sum(s * s for s in samples) / len(samples)) * self._gain)

                # 2. Band Energy Approximations
                # Low-pass filter (Bass): successive difference smoothing
                bass_samples = []
                prev = 0.0
                for s in samples:
                    val = 0.85 * prev + 0.15 * s
                    bass_samples.append(val)
                    prev = val
                bass = min(1.0, math.sqrt(sum(b * b for b in bass_samples) / len(bass_samples)) * self._gain * 1.5)

                # High-pass filter (Highs): subtraction of low pass
                high_samples = [samples[i] - bass_samples[i] for i in range(len(samples))]
                highs = min(1.0, math.sqrt(sum(h * h for h in high_samples) / len(high_samples)) * self._gain * 1.8)

                # Mids: overall minus extremes
                mids = min(1.0, max(0.0, rms * 1.2 - (bass * 0.4 + highs * 0.4)))

                # Exponential smoothing for visualizer and LED
                self._current_bass = 0.7 * self._current_bass + 0.3 * bass
                self._current_mids = 0.7 * self._current_mids + 0.3 * mids
                self._current_highs = 0.7 * self._current_highs + 0.3 * highs
                self._current_peak = 0.6 * self._current_peak + 0.4 * peak

                # Beat detection via moving average
                self._bass_history.append(bass)
                if len(self._bass_history) > 20:
                    self._bass_history.pop(0)
                avg_bass = sum(self._bass_history) / len(self._bass_history)
                is_beat = (bass > 0.3) and (bass > avg_bass * 1.45)

                if is_beat:
                    self.beat_detected.emit()

                # Emit metrics to UI
                self.metrics_updated.emit(self._current_bass, self._current_mids, self._current_highs, self._current_peak)

                # Send live LED packet to mouse (~35 FPS)
                now = time.time()
                if now - last_led_time >= 0.025:
                    last_led_time = now
                    r, g, b = self._calculate_led_color(is_beat, now)
                    # Send to zone 0 (primary backlight strip)
                    self.driver.send_live_led(0, r, g, b)

        finally:
            self._pa_simple_free(stream)
            self._running = False
            try:
                self.driver.restore_hardware_mode()
            except Exception:
                pass
            self.status_changed.emit(False, "Audio sync stopped")

    def _calculate_led_color(self, is_beat: bool, current_time: float) -> Tuple[int, int, int]:
        """Calculates dynamic RGB values based on selected audio reactive mode."""
        if self._mode == "bass_pulse":
            # Pulses primary color with intensity following bass & kicks
            intensity = max(0.05, min(1.0, self._current_bass * 1.2))
            if is_beat:
                # Flash secondary accent color on kick
                intensity = 1.0
                return (
                    int(self._secondary_color[0] * intensity),
                    int(self._secondary_color[1] * intensity),
                    int(self._secondary_color[2] * intensity),
                )
            return (
                int(self._color[0] * intensity),
                int(self._color[1] * intensity),
                int(self._color[2] * intensity),
            )

        elif self._mode == "spectrum":
            # Bass -> Red, Mids -> Green, Highs -> Blue
            r = int(min(255, self._current_bass * 255))
            g = int(min(255, self._current_mids * 255))
            b = int(min(255, self._current_highs * 255))
            return (r, g, b)

        elif self._mode == "neon_flow":
            # Color cycle where audio tempo controls rotation speed
            speed = 1.0 + (self._current_bass * 4.0)
            phase = (current_time * speed) % 6.28
            r = int((math.sin(phase) * 0.5 + 0.5) * 255 * self._current_peak)
            g = int((math.sin(phase + 2.09) * 0.5 + 0.5) * 255 * self._current_peak)
            b = int((math.sin(phase + 4.18) * 0.5 + 0.5) * 255 * self._current_peak)
            return (r, g, b)

        elif self._mode == "strobe":
            # Sharp flashing beat drops, black in quiet parts
            if is_beat or self._current_bass > 0.6:
                return (255, 255, 255)
            elif self._current_peak > 0.2:
                dim = int(self._current_peak * 120)
                return (dim, dim, dim)
            return (0, 0, 0)

        # Fallback
        return self._color
