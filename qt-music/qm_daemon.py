#!/usr/bin/env python3
"""Headless qt-music daemon (GLib + GStreamer + MPRIS + Unix socket IPC, zero Qt)."""
from __future__ import annotations

import ctypes
import fcntl
import hashlib
import io
import json
import os
os.environ.setdefault('GIO_USE_VFS', 'local')
import random
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)
from pathlib import Path

import qm_core
from qm_core import (
    AUDIO_EXT, CACHE, Library, Shuffler, _normalize_settings, _uri_from_path,
    load_art, load_lyrics, online_available, parse_lrc, path_from_url,
    repair_audio, resolve_stream, upgrade_lyrics, yt_album_tracks, yt_radio, yt_search,
)

ART = CACHE / 'art'
OFFSET_FILE = CACHE / 'offset.json'

# ───────────────────────────── own player: library, shuffle, queue, MPRIS ─────────────────────────────

_MAIN_THREAD_ID = threading.get_ident()
_GLib = None
_Gio = None
_Gst = None


def _ensure_glib():
    """Import GLib and Gio lazily for headless daemon & MPRIS."""
    global _GLib, _Gio
    if _GLib is None:
        import gi
        gi.require_version("Gio", "2.0")
        from gi.repository import Gio, GLib
        _GLib, _Gio = GLib, Gio
    return _GLib, _Gio


def _ensure_gst():
    """Import and initialize GStreamer lazily for headless audio playback."""
    global _Gst
    if _Gst is None:
        import gi
        gi.require_version("Gst", "1.0")
        from gi.repository import Gst
        Gst.init(None)
        _Gst = Gst
    return _Gst


def _trim_heap():
    """Return freed C heap pages to the OS after bursts like library/art scans."""
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:
        pass



class ThreadSafeSignal:
    """Lightweight GLib-dispatched signal replacing PySide6 Signal in the daemon."""

    def __init__(self):
        self._cbs = []

    def connect(self, cb):
        if cb not in self._cbs:
            self._cbs.append(cb)

    def emit(self, *args):
        if not self._cbs:
            return
        if threading.get_ident() == _MAIN_THREAD_ID or _GLib is None:
            for cb in list(self._cbs):
                cb(*args)
        else:
            def _dispatch():
                for cb in list(self._cbs):
                    cb(*args)
                return False
            _GLib.idle_add(_dispatch)


class GLibTimer:
    """Lightweight interval timer backed by GLib.timeout_add (zero Qt overhead)."""

    def __init__(self, _parent=None):
        self._interval_ms = 250
        self._cbs = []
        self._source_id = 0
        self.timeout = ThreadSafeSignal()

    def setInterval(self, ms):
        self._interval_ms = max(10, int(ms))

    def start(self, ms=None):
        if ms is not None:
            self.setInterval(ms)
        self.stop()
        glib, _ = _ensure_glib()

        def _fire():
            self.timeout.emit()
            return True

        self._source_id = glib.timeout_add(self._interval_ms, _fire)

    def stop(self):
        if self._source_id and _GLib is not None:
            try:
                _GLib.source_remove(self._source_id)
            except Exception:
                pass
        self._source_id = 0

    @staticmethod
    def singleShot(ms, cb):
        glib, _ = _ensure_glib()

        def _once():
            cb()
            return False

        glib.timeout_add(max(0, int(ms)), _once)


AUDIO_EXT = {".mp3", ".m4a", ".flac", ".ogg", ".opus", ".wav", ".aac", ".wma", ".mp4"}


# ───── playback engines (GStreamer playbin for low-RAM headless daemon, NullEngine for tests)
class GstEngine:
    """Headless audio engine powered directly by GStreamer playbin (~45 MB total daemon RSS)."""

    def __init__(self):
        self.ended = ThreadSafeSignal()
        self.failed = ThreadSafeSignal()
        self.stateChanged = ThreadSafeSignal()
        self.durationChanged = ThreadSafeSignal()
        self.Gst = _ensure_gst()
        self.pb = self.Gst.ElementFactory.make("playbin", "qt-music-player")
        if not self.pb:
            raise RuntimeError("GStreamer playbin unavailable (install gstreamer / gst-plugins-base)")
        # Audio + soft-volume only; explicitly disable video/text rendering in daemon
        self.pb.set_property("flags", (1 << 1) | (1 << 4))
        vsink = self.Gst.ElementFactory.make("fakesink", "fake-video")
        if vsink:
            self.pb.set_property("video-sink", vsink)
        for sink_name in ("pipewiresink", "pulsesink", "autoaudiosink"):
            asink = self.Gst.ElementFactory.make(sink_name, None)
            if asink:
                if sink_name in ("pipewiresink", "pulsesink"):
                    if asink.find_property("client-name"):
                        asink.set_property("client-name", "qt-music")
                    if asink.find_property("stream-properties"):
                        st_props = self.Gst.Structure.new_from_string("props,application.name=qt-music,media.role=music")
                        if st_props:
                            asink.set_property("stream-properties", st_props)
                self.pb.set_property("audio-sink", asink)
                break
        self._state = "Stopped"
        self._want_playing = False
        self._buffering = False
        self._switching = False
        self._load_gen = 0
        self._last_pos = 0.0
        self._duration = 0.0
        self._pending_seek = None
        bus = self.pb.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_bus_msg)

    def _on_bus_msg(self, _bus, msg):
        t = msg.type
        G = self.Gst
        if t == G.MessageType.EOS:
            if not self._switching and self._want_playing:
                self._want_playing = False
                self._state = "Stopped"
                self.ended.emit()
        elif t == G.MessageType.ERROR:
            err, _dbg = msg.parse_error()
            self._want_playing = False
            self._buffering = False
            self.pb.set_state(G.State.NULL)
            if not self._switching:
                self._state = "Stopped"
                self.failed.emit(str(err) or "playback error")
        elif t == G.MessageType.BUFFERING:
            pct = msg.parse_buffering()
            if pct < 100:
                if not self._buffering:
                    self._buffering = True
                    if self._want_playing:
                        self.pb.set_state(G.State.PAUSED)
            else:
                if self._buffering:
                    self._buffering = False
                    if self._want_playing:
                        self.pb.set_state(G.State.PLAYING)
        elif t == G.MessageType.ASYNC_DONE:
            ok, dur_ns = self.pb.query_duration(G.Format.TIME)
            if ok and dur_ns > 0:
                dur = dur_ns / G.SECOND
                if abs(dur - self._duration) > 0.2:
                    self._duration = dur
                    self.durationChanged.emit(dur)
            if self._pending_seek is not None:
                s = self._pending_seek
                self._pending_seek = None
                self.seek(s)
        elif t == G.MessageType.STATE_CHANGED and msg.src == self.pb:
            _old, new, _pend = msg.parse_state_changed()
            if self._buffering or self._switching:
                return
            # Ignore READY/NULL during preroll or pause; only stop()/EOS/ERROR sets Stopped.
            if new == G.State.PLAYING:
                st = "Playing"
            elif new == G.State.PAUSED:
                if self._want_playing:
                    return  # transient preroll READY->PAUSED on path to PLAYING
                st = "Paused"
            else:
                return
            if st != self._state:
                self._state = st
                self.stateChanged.emit(st)

    def _load_uri(self, uri, length=0.0):
        self._load_gen += 1
        self._switching = True
        self._buffering = False
        self._want_playing = False
        self._last_pos = 0.0
        self._duration = float(length or 0.0)
        self._pending_seek = None
        self.pb.set_state(self.Gst.State.READY)
        self.pb.set_property("uri", uri)

    def load(self, path):
        self._load_uri(_uri_from_path(path))

    def load_url(self, url, length=0.0):
        self._load_uri(str(url), length)

    def play(self):
        ensure_polybar_music()
        self._switching = False
        self._want_playing = True
        if not self._buffering:
            self.pb.set_state(self.Gst.State.PLAYING)
        if self._state != "Playing":
            self._state = "Playing"
            self.stateChanged.emit("Playing")

    def pause(self):
        self._last_pos = self.position()
        self._want_playing = False
        self._buffering = False
        self.pb.set_state(self.Gst.State.PAUSED)
        if self._state != "Paused":
            self._state = "Paused"
            self.stateChanged.emit("Paused")

    def stop(self):
        self._want_playing = False
        self._buffering = False
        self._switching = False
        self.pb.set_state(self.Gst.State.NULL)
        self._state = "Stopped"

    def position(self):
        if self._state == "Stopped" and not self._want_playing:
            return self._last_pos
        ok, pos_ns = self.pb.query_position(self.Gst.Format.TIME)
        if ok and pos_ns >= 0:
            self._last_pos = pos_ns / self.Gst.SECOND
        return self._last_pos

    def seek(self, sec):
        sec = max(0.0, float(sec))
        self._last_pos = sec
        ok = self.pb.seek_simple(
            self.Gst.Format.TIME,
            self.Gst.SeekFlags.FLUSH | self.Gst.SeekFlags.KEY_UNIT,
            int(sec * self.Gst.SECOND),
        )
        if not ok:
            self._pending_seek = sec

    def set_volume(self, v):
        self.pb.set_property("volume", max(0.0, min(1.0, float(v))))


class NullEngine:
    """No audio: advances a clock in real time (LYRICVIEW_ENGINE=null, used by the tests)."""

    def __init__(self):
        self.ended = ThreadSafeSignal()
        self.failed = ThreadSafeSignal()
        self.stateChanged = ThreadSafeSignal()
        self.durationChanged = ThreadSafeSignal()
        self.state, self.base, self.t0, self.dur = "Stopped", 0.0, time.time(), 0.0
        self.speed = float(os.environ.get("LYRICVIEW_NULL_SPEED", "1"))
        self.tm = GLibTimer()
        self.tm.setInterval(50)
        self.tm.timeout.connect(self._tick)
        self.tm.start()

    def _tick(self):
        if self.state == "Playing" and self.dur and self.position() >= self.dur:
            self.state = "Stopped"
            self.base = self.dur
            self.stateChanged.emit("Stopped")
            self.ended.emit()

    def load(self, path):
        self.base, self.t0, self.state = 0.0, time.time(), "Stopped"
        self.dur = next((t["len"] for t in getattr(self, "tracks", []) if t["path"] == path), 0) or 30.0
        if os.environ.get("LYRICVIEW_FAIL_FIRST") and "/fixed/" not in path and path not in self.__dict__.setdefault("_bad", set()):
            self._bad.add(path)
            self.dur = 30.0
            GLibTimer.singleShot(60, lambda: self.failed.emit("Demuxing failed"))

    def load_url(self, url, length=0.0):
        self.base, self.t0, self.state, self.dur = 0.0, time.time(), "Stopped", length or 30.0

    def play(self):
        ensure_polybar_music()
        self.t0, self.state = time.time(), "Playing"
        self.stateChanged.emit("Playing")

    def pause(self):
        self.base, self.state = self.position(), "Paused"
        self.stateChanged.emit("Paused")

    def stop(self):
        self.base, self.state = 0.0, "Stopped"

    def position(self): return self.base + ((time.time() - self.t0) * self.speed if self.state == "Playing" else 0)
    def seek(self, sec): self.base, self.t0 = max(0.0, sec), time.time()
    def set_volume(self, v): pass


# ───── MPRIS server (Gio), so playerctl / polybar can see and control what we play
MPRIS_XML = """<node>
 <interface name="org.mpris.MediaPlayer2">
  <method name="Raise"/><method name="Quit"/>
  <property name="CanQuit" type="b" access="read"/><property name="CanRaise" type="b" access="read"/>
  <property name="HasTrackList" type="b" access="read"/><property name="Identity" type="s" access="read"/>
  <property name="SupportedUriSchemes" type="as" access="read"/><property name="SupportedMimeTypes" type="as" access="read"/>
 </interface>
 <interface name="org.mpris.MediaPlayer2.Player">
  <method name="Next"/><method name="Previous"/><method name="Pause"/><method name="PlayPause"/><method name="Stop"/><method name="Play"/>
  <method name="Seek"><arg direction="in" name="Offset" type="x"/></method>
  <method name="SetPosition"><arg direction="in" name="TrackId" type="o"/><arg direction="in" name="Position" type="x"/></method>
  <method name="OpenUri"><arg direction="in" name="Uri" type="s"/></method>
  <signal name="Seeked"><arg name="Position" type="x"/></signal>
  <property name="PlaybackStatus" type="s" access="read"/><property name="Rate" type="d" access="read"/>
  <property name="Metadata" type="a{sv}" access="read"/><property name="Volume" type="d" access="readwrite"/>
  <property name="Position" type="x" access="read"/><property name="MinimumRate" type="d" access="read"/>
  <property name="MaximumRate" type="d" access="read"/><property name="CanGoNext" type="b" access="read"/>
  <property name="CanGoPrevious" type="b" access="read"/><property name="CanPlay" type="b" access="read"/>
  <property name="CanPause" type="b" access="read"/><property name="CanSeek" type="b" access="read"/>
  <property name="CanControl" type="b" access="read"/>
 </interface>
</node>"""
MPRIS_PATH, MPRIS_NAME = "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.lyricview"


def is_polybar_music_running() -> bool:
    """Check if an active (non-zombie) PolybarMusic process is running."""
    try:
        for entry in os.scandir("/proc"):
            if entry.name.isdigit():
                try:
                    with open(os.path.join(entry.path, "stat"), "rb") as f:
                        parts = f.read().split()
                        if len(parts) >= 3 and parts[1] == b"(PolybarMusic)" and parts[2] != b"Z":
                            return True
                except (FileNotFoundError, ProcessLookupError, PermissionError, IndexError):
                    continue
    except Exception:
        pass
    return False


def ensure_polybar_music():
    """Ensure PolybarMusic daemon is running for Polybar streaming widget."""
    try:
        if is_polybar_music_running():
            return
        poly_bin = shutil.which("PolybarMusic")
        if not poly_bin:
            for candidate in (
                os.path.expanduser("~/.config/bspwm/bin/PolybarMusic"),
                os.path.expanduser("~/.local/bin/PolybarMusic"),
            ):
                if os.path.exists(candidate) and os.access(candidate, os.X_OK):
                    poly_bin = candidate
                    break
        if poly_bin and os.path.exists(poly_bin):
            subprocess.Popen(
                [poly_bin, "--fifo"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                close_fds=True,
            )
    except Exception:
        pass


class Mpris:
    """Thread-safe MPRIS2 D-Bus server running on the main GLib loop."""

    def __init__(self, on_cmd, name="qt-music"):
        self.on_cmd = on_cmd  # called on main GLib loop: on_cmd(name, arg)
        self.name = "org.mpris.MediaPlayer2." + name
        self.status, self.meta, self.pos_us, self.t, self.vol = "Stopped", {}, 0, time.time(), 1.0
        self.conn = self.owner = None
        self.active = False
        self._lock = threading.Lock()
        self._emit_pending = False
        self._pending_changed = set()
        self._pending_seeked = False

    def start(self):
        if self.active:
            return True
        try:
            GLib, Gio = _ensure_glib()
        except Exception as e:
            print(f"qt-music: playerctl/polybar can't see this player - python-gobject is missing ({e})", file=sys.stderr)
            return False
        self.Gio, self.GLib = Gio, GLib
        self.info = Gio.DBusNodeInfo.new_for_xml(MPRIS_XML)
        self.owner = Gio.bus_own_name(
            Gio.BusType.SESSION, self.name, Gio.BusNameOwnerFlags.NONE,
            self._acquired, None,
            lambda c, n: print(f"qt-music: could not take the MPRIS name {n}", file=sys.stderr),
        )
        self.active = True
        return True

    def stop(self):
        with self._lock:
            self.status = "Stopped"
        if self.conn:
            try:
                self._emit_now({"PlaybackStatus"}, False)
            except Exception:
                pass
        owner = self.owner
        self.owner = None
        self.conn = None
        self.active = False
        if owner and hasattr(self, "Gio"):
            try:
                self.Gio.bus_unown_name(owner)
            except Exception:
                pass

    def _ensure_polybar_music(self):
        ensure_polybar_music()

    def ensure_polybar_music(self):
        ensure_polybar_music()

    def _set_playback_status(self, status):
        with self._lock:
            changed = (status != self.status)
            self.status = status
        if changed and status == "Playing":
            ensure_polybar_music()

    def _acquired(self, conn, name):
        self.conn = conn
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # Gio.DBusConnection.register_object is deprecated but still the portable call
            for iface in self.info.interfaces:
                conn.register_object(MPRIS_PATH, iface, self._call, self._get, None)
        ensure_polybar_music()

    def _call(self, conn, sender, path, iface, method, params, inv):
        a = params.unpack()
        if method in ("Next", "Previous", "Pause", "PlayPause", "Stop", "Play", "Quit"):
            self.on_cmd(method, 0.0)
        elif method == "Seek":
            self.on_cmd("Seek", a[0] / 1e6)
        elif method == "SetPosition":
            self.on_cmd("SetPosition", a[1] / 1e6)
        elif method == "OpenUri":
            self.on_cmd("OpenUri", str(a[0]))
        inv.return_value(self.GLib.Variant("()", ()))

    def _pos_unlocked(self):
        return self.pos_us + ((time.time() - self.t) * 1e6 if self.status == "Playing" else 0)

    def _meta_variant_unlocked(self):
        V, m = self.GLib.Variant, dict(self.meta)
        if not m:
            return V("a{sv}", {})
        d = {
            "mpris:trackid": V("o", "/org/lyricview/track/" + m["key"]),
            "mpris:length": V("x", int(max(0, m.get("length", 0)) * 1e6)),
            "xesam:title": V("s", m.get("title", "")),
            "xesam:album": V("s", m.get("album", "")),
            "xesam:artist": V("as", [m.get("artist", "")]),
            "xesam:url": V("s", m.get("url", "")),
        }
        if m.get("art"):
            d["mpris:artUrl"] = V("s", m["art"])
        return V("a{sv}", d)

    def _get(self, conn, sender, path, iface, prop):
        V = self.GLib.Variant
        if iface == "org.mpris.MediaPlayer2":
            return {
                "CanQuit": V("b", True), "CanRaise": V("b", False), "HasTrackList": V("b", False),
                "Identity": V("s", "qt-music"),
                "SupportedUriSchemes": V("as", ["file", "http", "https"]),
                "SupportedMimeTypes": V("as", ["audio/mpeg", "audio/mp4", "audio/flac", "audio/ogg"]),
            }.get(prop)
        with self._lock:
            return {
                "PlaybackStatus": V("s", self.status), "Rate": V("d", 1.0),
                "MinimumRate": V("d", 1.0), "MaximumRate": V("d", 1.0),
                "Metadata": self._meta_variant_unlocked(), "Volume": V("d", self.vol),
                "Position": V("x", int(self._pos_unlocked())),
                "CanGoNext": V("b", True), "CanGoPrevious": V("b", True),
                "CanPlay": V("b", True), "CanPause": V("b", True),
                "CanSeek": V("b", True), "CanControl": V("b", True),
            }.get(prop)

    def update(self, status=None, meta=None, pos=None, vol=None, seeked=False):
        changed = []
        with self._lock:
            if status is not None and status != self.status:
                self.status = status
                changed.append("PlaybackStatus")
            if meta is not None:
                self.meta = dict(meta)
                changed.append("Metadata")
            if vol is not None and vol != self.vol:
                self.vol = vol
                changed.append("Volume")
            if pos is not None:
                self.pos_us, self.t = int(pos * 1e6), time.time()
            need_pb = (status == "Playing" and bool(changed))
            if changed or seeked:
                self._pending_changed.update(changed)
                if seeked:
                    self._pending_seeked = True
                schedule = (not self._emit_pending) and self.active
                if schedule:
                    self._emit_pending = True
            else:
                schedule = False
        if need_pb:
            self._ensure_polybar_music()
        if schedule:
            if threading.get_ident() == _MAIN_THREAD_ID:
                self._flush_emit()
            else:
                self.GLib.idle_add(self._flush_emit)

    def _emit_now(self, keys, seeked):
        if not self.conn:
            return
        V = self.GLib.Variant
        with self._lock:
            props = {}
            for k in keys:
                if k == "PlaybackStatus":
                    props[k] = V("s", self.status)
                elif k == "Metadata":
                    props[k] = self._meta_variant_unlocked()
                elif k == "Volume":
                    props[k] = V("d", self.vol)
            pos_us = int(self._pos_unlocked())
        try:
            if props:
                self.conn.emit_signal(
                    None, MPRIS_PATH, "org.freedesktop.DBus.Properties", "PropertiesChanged",
                    V("(sa{sv}as)", ("org.mpris.MediaPlayer2.Player", props, [])),
                )
            if seeked:
                self.conn.emit_signal(
                    None, MPRIS_PATH, "org.mpris.MediaPlayer2.Player", "Seeked", V("(x)", (pos_us,)),
                )
        except Exception:
            pass

    def _flush_emit(self):
        with self._lock:
            keys = set(self._pending_changed)
            seeked = self._pending_seeked
            self._pending_changed.clear()
            self._pending_seeked = False
            self._emit_pending = False
        if keys or seeked:
            self._emit_now(keys, seeked)
        return False


class OwnPlayer:
    """Plays the library itself: queue first, otherwise the random album/song shuffle."""

    def __init__(self, bridge, lib, engine, volume, mpris_name="qt-music"):
        self.b, self.lib, self.shuf = bridge, lib, Shuffler(lib)
        self.eng = engine
        if isinstance(engine, NullEngine):
            engine.tracks = lib.tracks
        self.queue, self.history, self.cur, self.status, self.meta = [], [], None, "Stopped", {}
        self.vol = volume
        self.eng.set_volume(volume)
        self.eng.ended.connect(self.next)
        self.eng.stateChanged.connect(self._state)
        self.eng.failed.connect(self._failed)
        if hasattr(self.eng, "durationChanged"):
            self.eng.durationChanged.connect(self._on_duration)
        self.mpris = Mpris(lambda n, a: self.mprisCmd.emit(n, a), mpris_name)
        self.mprisCmd = ThreadSafeSignal()
        self.mprisCmd.connect(self._on_mpris)
        self.tick = GLibTimer()
        self.tick.setInterval(250)
        self.tick.timeout.connect(self._tick)
        self._fails = 0
        self._gen, self.radio, self.radio_seed, self.radio_failed, self._want_radio = 0, [], None, False, False
        self.streamReady = ThreadSafeSignal()
        self.repaired = ThreadSafeSignal()
        self.radioReady = ThreadSafeSignal()
        self.streamReady.connect(self._on_stream)
        self.repaired.connect(self._on_repaired)
        self._repaired, self._fail_gen = False, -1
        self.radioReady.connect(self._on_radio)

    def ensure_polybar_music(self):
        ensure_polybar_music()

    def _on_duration(self, dur):
        if self.meta and dur > 0 and abs(float(self.meta.get("length") or 0) - dur) > 1.0:
            self.meta = dict(self.meta, length=float(dur))
            self.mpris.update(meta=self.meta)
            self.b.ownDuration(float(dur))

    def _set_playback_status(self, status):
        """Update playback status, manage 250ms tick only while playing, and keep MPRIS/GUI in sync."""
        self.status = status
        if status == "Playing":
            ensure_polybar_music()
            self.tick.start()
        else:
            self.tick.stop()
        pos = self.eng.position()
        self.mpris.update(status=status, pos=pos)
        self.b.ownStatus(status == "Playing", pos)

    def on_track_loaded(self):
        """Hook called when a new track is loaded into the engine and ready for playback."""
        ensure_polybar_music()

    # ---- library rescans re-number tracks, so remember them by path
    def _enc(self, x):
        if isinstance(x, dict) and x.get("group"):
            return dict(x, tracks=[y for y in (self._enc(t) for t in x["tracks"]) if y is not None])
        if isinstance(x, dict):
            return x
        return self.lib.tracks[x]["path"] if isinstance(x, int) and x < len(self.lib.tracks) else None

    def _dec(self, x):
        if isinstance(x, dict) and x.get("group"):
            return dict(x, tracks=[y for y in (self._dec(t) for t in x["tracks"]) if y is not None])
        if isinstance(x, dict):
            return x
        return self.lib.by_path.get(x)

    def snapshot(self):
        return (self._enc(self.cur) if self.cur is not None else None, [e for e in map(self._enc, self.queue) if e is not None],
                [e for e in map(self._enc, self.history) if e is not None])

    def restore(self, snap):
        cur, q, h = snap
        self.cur = self._dec(cur) if cur is not None else None
        self.queue, self.history = [e for e in map(self._dec, q) if e is not None], [e for e in map(self._dec, h) if e is not None]
        self.shuf.left = {}
        if isinstance(self.eng, NullEngine):
            self.eng.tracks = self.lib.tracks

    # ---- lifecycle
    def activate(self):
        if not self.mpris.start():
            self.b.toast.emit("polybar/playerctl can't see this player (python-gobject missing)")
        if self.cur is None:
            if getattr(self.b.a, "track", None) is not None:
                self.play(self.b.a.track)
            else:
                self.next()
            if getattr(self.b.a, "seek", None) is not None:
                self.seek(self.b.a.seek)
                self.b.a.seek = None
        else:  # coming back from "follow": put the UI back on this track, then resume the sound
            self.b.ownResume()
            ensure_polybar_music()
            self._set_playback_status("Playing")
            self.mpris.update(status="Playing", meta=self.meta, pos=self.eng.position(), seeked=True)
            self.eng.play()
        self._push()

    def deactivate(self):
        self.tick.stop()
        if hasattr(self.eng, "stop"):
            self.eng.stop()
        elif self.status == "Playing":
            self.eng.pause()
        self.mpris.stop()

    # ---- transport
    def play(self, i, record=True):
        if isinstance(i, dict):
            return self._play_online(i, record)
        if i is None or not self.lib.tracks:
            self.b.toast.emit("your music folder has no songs yet")
            return
        t = self.lib.tracks[i]
        if not os.path.exists(t["path"]):
            self._fails += 1
            return self.next() if self._fails < 20 else None
        if record and self.cur is not None:
            self.history.append(self.cur)
            del self.history[:-200]
        self._fails = 0
        self._gen += 1
        self._repaired = False
        self.shuf.mark(i)
        self.cur = i
        self.eng.load(t["path"])
        if isinstance(self.eng, NullEngine):
            self.eng.dur = t["len"] or 240.0
        self.on_track_loaded()
        self.eng.play()
        ensure_polybar_music()
        self.meta = {"key": hashlib.md5(t["path"].encode()).hexdigest()[:16], "artist": t["artist"], "title": t["title"],
                     "album": t["album"], "length": t["len"], "url": _uri_from_path(t["path"]), "art": ""}
        self._set_playback_status("Playing")
        self.b.ownTrack(self.meta)
        self.b.sync.emit(0.0, True)
        self.mpris.update(status="Playing", meta=self.meta, pos=0.0, seeked=True)

    def reshuffle(self):
        self.queue.clear()
        self.history.clear()
        self.radio.clear()
        self.radio_seed = None
        self._want_radio = False
        self.cur = None
        self.shuf.reset()
        self.next()

    def next(self):
        if self.queue:
            return self.play(self._pop_queue())
        if self.radio:
            return self.play(self.radio.pop(0))
        if isinstance(self.cur, dict) and not self.radio_failed:  # streaming: wait for YouTube Music's radio
            self._want_radio = True
            self.b.toast.emit("finding something similar…")
            return
        self.play(self.shuf.next())

    # ---- online
    def _play_online(self, it, record=True):
        if record and self.cur is not None:
            self.history.append(self.cur)
            del self.history[:-200]
        self._gen += 1
        gen, self.cur, self._want_radio = self._gen, it, False
        self.meta = {"key": "yt" + hashlib.md5(it["id"].encode()).hexdigest()[:14], "artist": it["artist"], "title": it["title"],
                     "album": it["album"], "length": it["len"], "url": "https://music.youtube.com/watch?v=" + it["id"], "art": it.get("art", "")}
        self.eng.pause()          # silent until the stream URL is ready; the lyric clock stays at 0 meanwhile
        self.status = "Paused"
        self.b.ownTrack(self.meta)
        self.b.ownStatus(False)
        self.b.sync.emit(0.0, False)
        self.mpris.update(status="Paused", meta=self.meta, pos=0.0, seeked=True)
        threading.Thread(target=self._resolve, args=(it["id"], gen), daemon=True).start()
        if len(self.radio) < 3 and self.radio_seed != it["id"]:
            self.radio_seed, self.radio_failed = it["id"], False
            threading.Thread(target=self._radio_job, args=(it["id"],), daemon=True).start()

    def _resolve(self, vid, gen):
        try:
            url = resolve_stream(vid)
        except Exception:
            url = ""
        self.streamReady.emit(gen, url)

    def _on_stream(self, gen, url):
        if gen != self._gen:
            return  # you skipped on while it was loading
        if not url:
            self.b.toast.emit("couldn't stream this one - skipping")
            return GLibTimer.singleShot(300, self.next)
        self.eng.load_url(url, self.cur.get("len", 0) if isinstance(self.cur, dict) else 0)
        self.on_track_loaded()
        self.eng.play()
        ensure_polybar_music()
        self._set_playback_status("Playing")

    def _radio_job(self, vid):
        try:
            tracks = yt_radio(vid)
        except Exception:
            tracks = []
        self.radioReady.emit(vid, json.dumps(tracks))

    def _on_radio(self, vid, js):
        if vid != self.radio_seed:
            return
        seen = {x["id"] for x in [self.cur] + self.history[-30:] if isinstance(x, dict)}
        self.radio = [t for t in json.loads(js) if t["id"] not in seen]
        self.radio_failed = not self.radio
        if self._want_radio:
            self._want_radio = False
            self.next()

    def prev(self):
        if self.eng.position() > 3 or not self.history:
            return self.seek(0)
        self.play(self.history.pop(), record=False)

    def toggle(self):
        if self.status == "Playing":
            self.eng.pause()
        else:
            ensure_polybar_music()
            self.eng.play()

    def seek(self, sec):
        self.eng.seek(sec)
        self.mpris.update(pos=sec, seeked=True)
        self.b.sync.emit(float(sec), self.status == "Playing")
        self.b._send_gui({"type": "sync", "pos": float(sec), "playing": self.status == "Playing"})

    def set_volume(self, v):
        self.vol = max(0.0, min(1.0, v))
        self.eng.set_volume(self.vol)
        self.mpris.update(vol=self.vol)
        return self.vol

    # ---- queue: entries are a song, an online song, or a group (an album/artist that can be expanded and re-ordered)
    @staticmethod
    def _entry(items, name, sub):
        items = list(items)
        return {"group": True, "name": name or "Selection", "sub": sub or "", "tracks": items} if len(items) > 1 else (items[0] if items else None)

    def play_now(self, idxs, name=None, sub=None):
        if idxs:
            self.radio.clear()
            self._want_radio = False
            self.radio_seed = None
            e = self._entry(idxs[1:], name, sub)
            self.queue = [e] if e is not None else []
            self.play(idxs[0])
            self.b._send_gui({"type": "queue", "rows": self.queue_rows()})

    def enqueue(self, idxs, name=None, sub=None):
        e = self._entry(idxs, name, sub)
        if e is not None:
            self.queue.append(e)
            self.b._send_gui({"type": "queue", "rows": self.queue_rows()})

    def _pop_queue(self):
        e = self.queue[0]
        if isinstance(e, dict) and e.get("group"):
            t = e["tracks"].pop(0)
            if not e["tracks"]:
                self.queue.pop(0)
            return t
        return self.queue.pop(0)

    def _row(self, t):
        if isinstance(t, dict):
            return {"name": t["title"], "sub": f"{t['artists']} · stream"}
        x = self.lib.tracks[t]
        return {"name": x["title"], "sub": f"{x['artist']} · {x['album']}"}

    def queue_rows(self):
        rows = []
        for e in self.queue:
            if isinstance(e, dict) and e.get("group"):
                rows.append({"name": e["name"], "sub": e["sub"], "group": True, "n": len(e["tracks"]), "kids": [self._row(t) for t in e["tracks"]]})
            else:
                rows.append(self._row(e))
        return rows

    def _box(self, path):
        return self.queue if len(path) == 1 else self.queue[path[0]]["tracks"]

    def queue_move(self, path, delta):
        box, i = self._box(path), path[-1]
        j = i + delta
        if 0 <= i < len(box) and 0 <= j < len(box):
            box[i], box[j] = box[j], box[i]
            self.b._send_gui({"type": "queue", "rows": self.queue_rows()})
            return True
        return False

    def queue_remove(self, path):
        box, i = self._box(path), path[-1]
        if 0 <= i < len(box):
            del box[i]
            if len(path) == 2 and not box:
                del self.queue[path[0]]
            self.b._send_gui({"type": "queue", "rows": self.queue_rows()})

    def queue_play(self, path):
        i = path[0]
        if not (0 <= i < len(self.queue)):
            return
        e = self.queue[i]
        if len(path) == 2 and isinstance(e, dict) and e.get("group") and path[1] < len(e["tracks"]):
            t, e["tracks"] = e["tracks"][path[1]], e["tracks"][path[1] + 1:]
            self.queue = self.queue[i:] if e["tracks"] else self.queue[i + 1:]
        elif isinstance(e, dict) and e.get("group"):
            t = e["tracks"].pop(0)
            self.queue = self.queue[i:] if e["tracks"] else self.queue[i + 1:]
        else:
            t, self.queue = e, self.queue[i + 1:]
        self.play(t)
        self.b._send_gui({"type": "queue", "rows": self.queue_rows()})

    # ---- engine events
    def _state(self, st):
        if st == "Stopped" and self.status == "Playing":
            return  # transient: end of media is followed by next()
        self._set_playback_status(st)

    def _failed(self, msg):
        if self._fail_gen == self._gen:
            return  # the backend reports the same failure several times
        self._fail_gen = self._gen
        if isinstance(self.cur, int) and not self._repaired and shutil.which("ffmpeg"):
            self._repaired, gen, path = True, self._gen, self.lib.tracks[self.cur]["path"]
            self.b.toast.emit("this file confuses the player - fixing it…")
            return threading.Thread(target=lambda: self.repaired.emit(gen, self._safe_repair(path)), daemon=True).start()
        self.b.toast.emit(f"can't play this file ({msg[:60]}) - skipping")
        GLibTimer.singleShot(400, self.next)

    @staticmethod
    def _safe_repair(path):
        try:
            return repair_audio(path) or ""
        except Exception:
            return ""

    def _on_repaired(self, gen, path):
        if gen != self._gen:
            return
        if not path:
            self.b.toast.emit("can't play this file - skipping")
            return GLibTimer.singleShot(400, self.next)
        self._fail_gen = -1
        self.eng.load(path)
        self.eng.play()

    def _tick(self):
        pos = self.eng.position()
        self.b.sync.emit(float(pos), self.status == "Playing")
        self.mpris.update(pos=pos)
        self.b._send_gui({"type": "sync", "pos": float(pos), "playing": self.status == "Playing"})

    def _push(self):
        pos = self.eng.position()
        self.b.sync.emit(float(pos), self.status == "Playing")
        self.b._send_gui({"type": "sync", "pos": float(pos), "playing": self.status == "Playing"})

    def _on_mpris(self, name, arg):
        if name == "Next": self.next()
        elif name == "Previous": self.prev()
        elif name == "Play": self.eng.play()
        elif name in ("Pause", "Stop"): self.eng.pause()
        elif name == "PlayPause": self.toggle()
        elif name == "Seek": self.seek(self.eng.position() + arg)
        elif name == "SetPosition": self.seek(arg)
        elif name == "OpenUri":
            p = path_from_url(arg) if str(arg).startswith("file://") else Path(str(arg))
            if p and p.exists():
                idx = self.lib.by_path.get(str(p.resolve()))
                if idx is not None:
                    self.play(idx)
                else:
                    self.play({"path": str(p), "title": p.stem, "artist": "Unknown", "album": "", "len": 0})
        elif name == "Quit":
            self.b.quitApp()


def palette(tiny_pil):
    """Two accent colours from a tiny RGB Pillow image (saturation/brightness weighted hue buckets)."""
    import colorsys
    bk = [[0.0, 0.0, 0.0, 0.0] for _ in range(12)]
    for r, g, b in tiny_pil.getdata():
        mx, mn = max(r, g, b), min(r, g, b)
        v = mx / 255.0
        if v < 0.2:
            continue
        s = (mx - mn) / mx if mx else 0.0
        w = s * s * v + 0.01
        h = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)[0]
        o = bk[int(h * 12) % 12]
        o[0] += w; o[1] += r * w; o[2] += g * w; o[3] += b * w
    bk.sort(key=lambda o: -o[0])
    if bk[0][0] <= 0:
        return "#6c5ce7", "#00b894"

    def lift(o):
        cs = [o[1] / o[0], o[2] / o[0], o[3] / o[0]]
        m = max(cs)
        if m < 150:
            cs = [v * 150 / max(m, 1) for v in cs]
        return "#%02x%02x%02x" % tuple(min(255, int(v)) for v in cs)

    c1 = lift(bk[0])
    return c1, (lift(bk[1]) if bk[1][0] > bk[0][0] * 0.25 else c1)


def cached_art(key):
    """Return cached art metadata dict without importing Pillow when already generated."""
    pj = ART / f"{key}.json"
    pa = ART / f"{key}.jpg"
    if pj.exists() and pa.exists():
        try:
            return json.loads(pj.read_text("utf-8"))
        except Exception:
            pass
    return None


def process_art(data, key):
    """Cover bytes -> square cover, fast smooth blurred bg/mid, and two accent colours via Pillow."""
    try:
        from PIL import Image as PilImage, ImageFilter
        with PilImage.open(io.BytesIO(data)) as raw_im:
            im = raw_im.convert("RGB")
            side = min(im.width, im.height)
            sq = im.crop(((im.width - side) // 2, (im.height - side) // 2,
                          (im.width + side) // 2, (im.height + side) // 2))
            ART.mkdir(parents=True, exist_ok=True)
            pa, pb, pm, pj = ART / f"{key}.jpg", ART / f"{key}-bg.jpg", ART / f"{key}-mid.jpg", ART / f"{key}.json"
            art_im = sq.resize((720, 720), PilImage.Resampling.LANCZOS) if side > 720 else sq
            art_im.save(str(pa), "JPEG", quality=90)
            # Downscale first before GaussianBlur: identical soft backdrop, ~10x faster and tiny RAM
            sq.resize((240, 240), PilImage.Resampling.BILINEAR).filter(ImageFilter.GaussianBlur(radius=16)).save(str(pb), "JPEG", quality=85)
            sq.resize((360, 360), PilImage.Resampling.BILINEAR).filter(ImageFilter.GaussianBlur(radius=14)).save(str(pm), "JPEG", quality=88)
            tiny = sq.resize((20, 20), PilImage.Resampling.BILINEAR)
            c1, c2 = palette(tiny)
        info = {"art": _uri_from_path(pa), "bg": _uri_from_path(pb), "card": _uri_from_path(pa), "mid": _uri_from_path(pm), "c1": c1, "c2": c2}
        try:
            pj.write_text(json.dumps(info), "utf-8")
        except OSError:
            pass
        _trim_heap()
        return info
    except Exception:
        return None


def prune_art(keep=250):
    try:
        files = sorted(list(ART.glob("*.jpg")) + list(ART.glob("*.png")), key=lambda p: p.stat().st_mtime, reverse=True)
        for p in files[keep * 3:]:
            p.unlink(missing_ok=True)
        tdir = CACHE / "thumbs"
        if tdir.exists():
            tfiles = sorted(tdir.glob("*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
            for p in tfiles[800:]:
                p.unlink(missing_ok=True)
    except OSError:
        pass


class Bridge:
    """Headless GLib daemon backend owning audio, library, lyrics, MPRIS, and GUI IPC."""

    def __init__(self, state_or_args, args=None):
        self.metaChanged = ThreadSafeSignal()
        self.lyricsChanged = ThreadSafeSignal()
        self.artChanged = ThreadSafeSignal()
        self.tuneChanged = ThreadSafeSignal()
        self.modeChanged = ThreadSafeSignal()
        self.libChanged = ThreadSafeSignal()
        self.sync = ThreadSafeSignal()
        self.toast = ThreadSafeSignal()
        self._libdone = ThreadSafeSignal()
        self.searchDone = ThreadSafeSignal()
        self.thumbsReady = ThreadSafeSignal()
        self.dlChanged = ThreadSafeSignal()
        self._modeReq = ThreadSafeSignal()
        self._thumbs = ThreadSafeSignal()
        self._dlsig = ThreadSafeSignal()
        self._srch = ThreadSafeSignal()
        self._meta = ThreadSafeSignal()  # worker thread -> main loop
        self._lyr = ThreadSafeSignal()
        self._art = ThreadSafeSignal()

        if args is None:
            self.a = state_or_args
            self.st = None
        else:
            self.st, self.a = state_or_args, args
        self.lib = Library(self.a.music or os.environ.get("MUSICD_DIR") or Path.home() / "Music")
        self.own, self._mode, self._own_key, self._scanning, self._engine_err = None, "own", None, False, ""
        self._set_file = CACHE / "settings.json"
        try:
            raw_settings = json.loads(self._set_file.read_text())
        except Exception:
            raw_settings = {}
        self._settings = _normalize_settings(raw_settings)
        self._meta_d = {"active": False, "playing": False, "title": "", "artist": "", "album": "", "length": 0.0}
        self._kind, self._lyr_json, self._src, self._raw, self._length = "none", "[]", "", None, 0.0
        self._art_d = {"art": "", "bg": "", "c1": "#6c5ce7", "c2": "#00b894"}
        self._own_ui = None
        self._cfg = {"windowed": bool(self.a.windowed or self.a.screenshot), "lite": bool(self.a.lite), "controls": bool(self.a.controls),
                     "wstyle": int(self._settings.get("wstyle", 0)),
                     "font": self.a.font or os.environ.get("LYRICVIEW_FONT") or "",
                     **self._settings}
        self._win = None
        self._gui_proc = None
        self._gui_sock = None
        self._gui_watch = 0
        self._gui_buf = b""
        self._loop = None
        self._socket_paths = []
        self._pid_file = None
        self._lock_fh = None
        try:
            self._offset = float(json.loads(OFFSET_FILE.read_text())["offset"])
        except Exception:
            self._offset = 0.0
        self._meta.connect(self._on_meta)
        self._lyr.connect(self._on_lyr)
        self._art.connect(self._on_art)
        self._libdone.connect(self._on_libdone)
        self._srch.connect(self._on_srch)
        self._modeReq.connect(lambda m: self.setMode(m))
        self._thumbs.connect(self.thumbsReady.emit)
        self._dlsig.connect(self.dlChanged.emit)
        self.toast.connect(lambda t: self._send_gui({"type": "toast", "msg": t}))
        self.thumbsReady.connect(lambda: self._send_gui({"type": "thumbsReady"}))
        self.dlChanged.connect(lambda d: self._send_gui({"type": "dlChanged", "data": d}))
        self.libChanged.connect(lambda: self._send_gui({"type": "libChanged", "info": self.libInfo}))
        self.searchDone.connect(lambda s: self._send_gui({"type": "searchDone", "data": s}))
        self._wordlevel, self._auto, self._auto_t, self._gone, self._thumb_busy, self._thumbs_started, self._dl, self._dl_id = False, False, 0.0, 0, False, False, [], 0
        self._sgen, self._sr = 0, {}

    @property
    def libInfo(self):
        return {"ready": self.lib.ready, "count": self.lib.count, "scanning": self._scanning,
                "dir": str(self.lib.root), "engineErr": self._engine_err, "online": online_available()}

    def _create_engine(self):
        if os.environ.get("LYRICVIEW_ENGINE") == "null":
            return NullEngine()
        return GstEngine()

    # ---- start-up: build the library in the background and start player
    def start(self):
        eng = None
        try:
            eng = self._create_engine()
        except Exception as e:
            self._engine_err = f"{type(e).__name__}: {e}"[:120]
            print(f"qt-music: audio engine error: {self._engine_err}", file=sys.stderr)
        if eng:
            self.own = OwnPlayer(self, self.lib, eng, float(self._settings.get("volume", 0.8)),
                                 self._settings.get("mpris_name") or self.a.mpris_name or "qt-music")
        self.lib.load_cache()
        self.setMode("own", announce=False)
        if not self.lib.ready:
            self._rescan(announce=False)
        self._rescan_timer = GLibTimer()
        self._rescan_timer.setInterval(30000)
        self._rescan_timer.timeout.connect(self._rescan)
        self._rescan_timer.start()
        # Defer cache pruning so startup playback is immediate
        GLibTimer.singleShot(10000, lambda: threading.Thread(target=prune_art, daemon=True).start())

    def _scan(self):
        try:
            self.lib.scan()
        except Exception as e:
            print(f"qt-music: library scan failed: {e!r}", file=sys.stderr)
        self._libdone.emit()

    def rescan(self):
        self._rescan(announce=True)

    def _rescan(self, announce=False):
        if self._scanning:
            return
        self._scanning = True
        if announce:
            self.toast.emit("rescanning your music…")
        threading.Thread(target=self._scan, daemon=True).start()

    def _on_libdone(self):
        changed = self.lib.pending is not None
        if changed:
            snap = self.own.snapshot() if self.own else None
            self.lib.apply_pending()
            if self.own:
                self.own.restore(snap)
            if self._gui_sock:
                self._start_thumbs()
        self._scanning = False
        if changed:
            self.libChanged.emit()
        if self.own and self.own.cur is None and self.lib.ready:
            self.own.activate()
        _trim_heap()

    def setMode(self, m="own", announce=True):
        self._mode = "own"
        if not self.own:
            try:
                eng = self._create_engine()
                self.own = OwnPlayer(self, self.lib, eng, float(self._settings.get("volume", 0.8)),
                                     self._settings.get("mpris_name") or self.a.mpris_name or "qt-music")
            except Exception as e:
                self._engine_err = f"{type(e).__name__}: {e}"[:120]
                self.toast.emit("can't play audio here - install gstreamer / gst-plugins (" + (self._engine_err or "unavailable") + ")")
                return
        if self.own and not self.own.mpris.active:
            self.own.mpris.start()
        self.modeChanged.emit()
        if self.lib.ready and self.own.cur is None:
            self.own.activate()
        if announce:
            self.toast.emit("your library · shuffling" if self.lib.ready else "scanning your music folder…")

    def toggleMode(self):
        self.reshuffle()

    def reshuffle(self):
        if self.own:
            was_streaming = isinstance(self.own.cur, dict)
            self.own.reshuffle()
            if was_streaming:
                self.toast.emit("exited streaming · playing library")
            else:
                self.toast.emit("reshuffled library")
            self._send_gui({"type": "queue", "rows": self.own.queue_rows()})

    # ---- own-player callbacks
    def ownTrack(self, meta):
        self._own_key = meta["key"]
        self._meta_d = {"active": True, "playing": True, "key": meta["key"], "title": meta["title"], "artist": meta["artist"],
                        "album": meta["album"], "length": float(meta["length"] or 0)}
        self.metaChanged.emit()
        self._send_gui({"type": "meta", "meta": self._meta_d})
        self._send_gui({"type": "queue", "rows": self.own.queue_rows() if self.own else []})
        self._on_lyr(json.dumps({"kind": "loading", "lines": []}))
        threading.Thread(target=self._own_assets, args=(dict(meta),), daemon=True).start()

    def ownDuration(self, dur):
        if self._meta_d.get("active"):
            self._meta_d = dict(self._meta_d, length=float(dur))
            self.metaChanged.emit()
            self._send_gui({"type": "meta", "meta": self._meta_d})

    def ownResume(self):
        u = self._own_ui
        if not u:
            return
        self._meta_d, self._kind, self._lyr_json, self._src, self._raw, self._length, self._art_d = u
        self._meta_d = dict(self._meta_d, active=True, playing=True)
        self._own_key = self._meta_d.get("key")
        self.metaChanged.emit()
        self.lyricsChanged.emit()
        self.artChanged.emit()

    def ownStatus(self, playing, pos=None):
        if pos is not None:
            self.sync.emit(float(pos), playing)
            self._send_gui({"type": "sync", "pos": float(pos), "playing": playing})
        if self._meta_d.get("playing") != playing:
            self._meta_d = dict(self._meta_d, playing=playing)
            self.metaChanged.emit()
            self._send_gui({"type": "status", "playing": playing})

    def _own_assets(self, meta):
        key = meta["key"]
        threading.Thread(target=self._own_art, args=(meta,), daemon=True).start()
        try:
            lyr = load_lyrics(meta)
        except Exception:
            lyr = None
        if self._own_key == key:
            self._lyr.emit(json.dumps(lyr or {"kind": "none", "lines": [], "src": ""}, ensure_ascii=False))
        try:  # not word-by-word? look again, every play
            up = upgrade_lyrics(meta, lyr or {})
        except Exception:
            up = None
        if up and self._own_key == key:
            self._lyr.emit(json.dumps(up, ensure_ascii=False))

    def _own_art(self, meta):
        try:
            info = cached_art(meta["key"])
            if not info:
                art = load_art(meta)
                info = process_art(art[0], meta["key"]) if art else None
        except Exception:
            info = None
        if info and self._own_key == meta["key"]:
            self._art.emit(json.dumps(info))
            if self.own:
                self.own.mpris.update(meta=dict(self.own.meta, art=info["art"]))

    # ---- picker data for the keyboard overlays: albums / artists (cover grids) and songs, with drill-down
    def _thumb_path(self, a):
        return CACHE / "thumbs" / (hashlib.md5(f"{a['artist']}|{a['name']}".lower().encode()).hexdigest()[:16] + ".jpg")

    def _thumb_url(self, a):
        p = self._thumb_path(a)
        return _uri_from_path(p) if p.exists() else ""

    def _start_thumbs(self):
        if self._thumb_busy or not self.lib.ready:
            return
        self._thumb_busy = True
        threading.Thread(target=self._thumb_job, daemon=True).start()

    def _thumb_job(self):
        made = 0
        try:
            from PIL import Image as PilImage
            (CACHE / "thumbs").mkdir(parents=True, exist_ok=True)
            for a in list(self.lib.albums.values()):
                p = self._thumb_path(a)
                if p.exists() or not a["tracks"]:
                    continue
                try:
                    art = load_art({"url": _uri_from_path(self.lib.tracks[a["tracks"][0]]["path"]), "art": ""})
                    if not art:
                        continue
                    with PilImage.open(io.BytesIO(art[0])) as raw_im:
                        im = raw_im.convert("RGB")
                        s = min(im.width, im.height)
                        sq = im.crop(((im.width - s) // 2, (im.height - s) // 2, (im.width + s) // 2, (im.height + s) // 2))
                        sq.resize((300, 300), PilImage.Resampling.LANCZOS).save(str(p), "JPEG", quality=82)
                    made += 1
                    if made % 8 == 0:
                        self._thumbs.emit()
                except Exception:
                    continue
            _trim_heap()
        finally:
            self._thumb_busy = False
            if made:
                self._thumbs.emit()

    def pickerData(self, spec):
        """spec: albums | artists | songs | albums:artist:ID | songs:album:ID"""
        kind, _, rest = spec.partition(":")
        lib = self.lib
        if kind == "albums":
            ids = None
            if rest.startswith("artist:") and int(rest[7:]) in lib.artists:
                ids = set(lib.artists[int(rest[7:])]["albums"])
            rows = [dict(r, thumb=self._thumb_url(lib.albums[r["id"]])) for r in lib.album_list() if ids is None or r["id"] in ids]
        elif kind == "artists":
            rows = []
            for r in lib.artist_list():
                first = lib.albums[lib.artists[r["id"]]["albums"][0]] if lib.artists[r["id"]]["albums"] else None
                rows.append(dict(r, thumb=self._thumb_url(first) if first else ""))
        else:  # songs
            if rest.startswith("album:") and int(rest[6:]) in lib.albums:
                idxs = lib.albums[int(rest[6:])]["tracks"]
            else:
                idxs = sorted(range(len(lib.tracks)), key=lambda i: (lib.tracks[i]["title"].lower(), lib.tracks[i]["artist"].lower()))
            rows = [{"id": i, "name": lib.tracks[i]["title"], "sub": f"{lib.tracks[i]['artist']} · {lib.tracks[i]['album']}", "n": 0,
                     "dur": f"{int(lib.tracks[i]['len'] // 60)}:{int(lib.tracks[i]['len'] % 60):02d}" if lib.tracks[i]["len"] else ""} for i in idxs]
        return json.dumps(rows, ensure_ascii=False)

    def pick(self, kind, ident, queue_only):
        if not self.own or not self.lib.ready:
            return
        lib, name, sub = self.lib, None, None
        if kind == "albums" and ident in lib.albums:
            idxs, name, sub = list(lib.albums[ident]["tracks"]), lib.albums[ident]["name"], lib.albums[ident]["artist"]
        elif kind == "artists" and ident in lib.artists:
            idxs, name, sub = lib.artist_tracks(ident), lib.artists[ident]["name"], "all songs"
        elif kind == "songs" and 0 <= ident < len(lib.tracks):
            idxs = [ident]
        else:
            return
        if not idxs:
            return
        n = len(idxs)
        if queue_only:
            self.own.enqueue(idxs, name, sub)
            self.toast.emit(f"queued {name or lib.tracks[idxs[0]]['title']}" + (f" · {n} songs" if n > 1 else ""))
        else:
            self.own.play_now(idxs, name, sub)
            self.toast.emit(f"playing {n} song{'s' if n != 1 else ''}, then shuffle" if n > 1 else "playing · shuffle after")

    # ---- online: search and stream
    def search(self, query, kind="songs"):
        self._sgen += 1
        gen = self._sgen
        query = (query or "").strip()
        if len(query) < 2:
            self._srch.emit(gen, json.dumps({"rows": [], "error": ""}))
            return
        if not online_available():
            self._srch.emit(gen, json.dumps({"rows": [], "error": "needs ytmusicapi and yt-dlp:  sudo pacman -S python-ytmusicapi yt-dlp"}))
            return

        def job():
            try:
                rows = yt_search(query, kind=kind)
                self._srch.emit(gen, json.dumps({"rows": rows, "error": ""}, ensure_ascii=False))
            except Exception as e:
                self._srch.emit(gen, json.dumps({"rows": [], "error": f"search failed ({type(e).__name__}) - are you online?"}))
        threading.Thread(target=job, daemon=True).start()

    def drillAlbum(self, browse_id):
        self._sgen += 1
        gen = self._sgen

        def job():
            try:
                rows = yt_album_tracks(browse_id)
                self._srch.emit(gen, json.dumps({"rows": rows, "error": ""}, ensure_ascii=False))
            except Exception as e:
                self._srch.emit(gen, json.dumps({"rows": [], "error": f"failed loading album ({type(e).__name__})"}))
        threading.Thread(target=job, daemon=True).start()

    def _on_srch(self, gen, js):
        if gen != self._sgen:
            return
        d = json.loads(js)
        self._sr = {r["id"]: r for r in d["rows"]}
        rows = [{"id": r["id"], "name": r["title"], "sub": f"{r['artists']}" + (f" · {r['album']}" if r["album"] else ""),
                 "dur": f"{int(r['len'] // 60)}:{int(r['len'] % 60):02d}" if r["len"] else ""} for r in d["rows"]]
        self.searchDone.emit(json.dumps({"rows": rows, "error": d["error"]}, ensure_ascii=False))

    def pickOnline(self, vid, queue_only):
        it = self._sr.get(vid)
        if not it or not self.own:
            return
        if queue_only:
            self.own.queue.append(it)
            self.toast.emit(f"queued · {it['title']}")
        else:
            self.own.queue, self.own.radio = [], []
            self.own.play(it)
            self.toast.emit("streaming · press M to return to library")

    def queueData(self):
        return json.dumps(self.own.queue_rows() if self.own else [], ensure_ascii=False)

    def queuePlay(self, path):
        if self.own:
            self.own.queue_play(json.loads(path))

    def queueRemove(self, path):
        if self.own:
            self.own.queue_remove(json.loads(path))

    def queueMove(self, path, delta):
        return bool(self.own and self.own.queue_move(json.loads(path), delta))

    def queueClear(self):
        if self.own:
            self.own.queue = []
            self.own.radio = []
            self.own._want_radio = False
            self.toast.emit("queue cleared")

    # ---- interactive downloads through musicD
    def _musicd(self):
        p = os.environ.get("LYRICVIEW_MUSICD") or shutil.which("musicD")
        if not p and Path(__file__).with_name("musicD").exists():
            p = str(Path(__file__).with_name("musicD"))
        return p

    def _dl_push(self):
        self._dlsig.emit(json.dumps(self._dl[-6:], ensure_ascii=False))

    def dlStart(self, vid, title, sub):
        self._dl_run("https://music.youtube.com/watch?v=" + vid, title, sub)

    def dlLink(self, url):
        self._dl_run(url.strip(), url.strip()[:60], "link")

    def _dl_run(self, url, title, sub):
        exe = self._musicd()
        self._dl_id += 1
        job = {"id": self._dl_id, "title": title, "sub": sub, "state": "queued", "note": ""}
        self._dl.append(job)
        if not exe:
            job.update(state="failed", note="musicD not found - put it in your PATH")
            return self._dl_push()
        self._dl_push()
        threading.Thread(target=self._dl_thread, args=(exe, url, job), daemon=True).start()

    def _dl_thread(self, exe, url, job):
        env = dict(os.environ, MUSICD_DIR=str(self.lib.root), NO_COLOR="1")
        try:
            p = subprocess.Popen([exe, "song", "-l", url, "-j", "1"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 encoding="utf-8", errors="replace", env=env)
            job["state"] = "starting"
            self._dl_push()
            for line in p.stdout:
                s = line.strip()
                if "Downloading" in s:
                    job.update(state="downloading", note="")
                elif "Embedding" in s:
                    job.update(state="tagging", note="")
                elif s.startswith("✔"):
                    job.update(state="done", note=s[1:].strip()[:80])
                elif s.startswith("⤼"):
                    job.update(state="done", note="already in your library")
                elif s.startswith("✘"):
                    job.update(state="failed", note=s[1:].strip()[:90])
                self._dl_push()
            p.wait()
            if job["state"] not in ("done", "failed"):
                job.update(state="failed" if p.returncode else "done", note=job["note"] or ("musicD exited with an error" if p.returncode else ""))
        except Exception as e:
            job.update(state="failed", note=f"{type(e).__name__}: {e}"[:90])
        self._dl_push()
        if job["state"] == "done":
            self.toast.emit(f"downloaded · {job['title']}")
            GLibTimer.singleShot(0, self._rescan)  # picks the new song up right away

    def _save(self, key, val):
        if hasattr(val, "toVariant"):
            val = val.toVariant()
        if isinstance(val, (int, float, str, bool, list, dict)) or val is None:
            self._settings[key] = val
        else:
            try:
                self._settings[key] = json.loads(json.dumps(val, default=str))
            except Exception:
                self._settings[key] = str(val)
        try:
            CACHE.mkdir(parents=True, exist_ok=True)
            self._set_file.write_text(json.dumps(self._settings, indent=2, default=str))
        except Exception as e:
            print(f"qt-music: save settings error: {e}", file=sys.stderr)

    def saveSetting(self, key, val):
        self._save(key, val)
        self._cfg[key] = self._settings.get(key, val)

    def _capture_prev_desktop(self):
        try:
            cur = subprocess.check_output(["bspc", "query", "-D", "-d", "focused", "--names"], encoding="utf-8", timeout=0.35).strip()
            if cur and cur != "5":
                self._prev_desktop = cur
        except Exception:
            pass

    def _post_show_desktop_5(self):
        try:
            subprocess.Popen(["bspc", "desktop", "5", "-f"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def _restore_prev_desktop(self):
        try:
            target = getattr(self, "_prev_desktop", None)
            desks = subprocess.check_output(["bspc", "query", "-D", "--names"], encoding="utf-8", timeout=0.35).split()
            if target and target in desks and target != "5":
                subprocess.Popen(["bspc", "desktop", target, "-f"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                cur = subprocess.check_output(["bspc", "query", "-D", "-d", "focused", "--names"], encoding="utf-8", timeout=0.35).strip()
                if cur == "5":
                    valid = [d for d in desks if d != "5"]
                    if valid:
                        subprocess.Popen(["bspc", "desktop", valid[0], "-f"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        self._prev_desktop = None

    def _close_gui_sock(self):
        if self._gui_watch and _GLib is not None:
            try:
                _GLib.source_remove(self._gui_watch)
            except Exception:
                pass
        self._gui_watch = 0
        if self._gui_sock is not None:
            try:
                self._gui_sock.close()
            except Exception:
                pass
        self._gui_sock = None
        self._gui_buf = b""

    def set_gui_client(self, conn):
        self._close_gui_sock()
        self._gui_sock = conn
        conn.setblocking(False)
        glib, _ = _ensure_glib()
        self._gui_watch = glib.io_add_watch(conn.fileno(), glib.IOCondition.IN | glib.IOCondition.HUP | glib.IOCondition.ERR,
                                            self._on_gui_io)
        if not self._thumbs_started:
            self._thumbs_started = True
            self._start_thumbs()
        try:
            init_data = {
                "type": "init",
                "meta": self._meta_d,
                "art": self._art_d,
                "lyrics": {
                    "kind": self._kind,
                    "lines": json.loads(self._lyr_json) if self._lyr_json else [],
                    "src": self._src,
                    "wordlevel": self._wordlevel,
                    "raw": self._raw,
                    "length": self._length,
                },
                "pos": float(self.own.eng.position()) if self.own else 0.0,
                "playing": (self.own.status == "Playing") if self.own else False,
                "volume": self.own.vol if self.own else float(self._settings.get("volume", 0.8)),
                "offset": self._offset,
                "spread": qm_core.SPREAD,
                "queue": self.own.queue_rows() if self.own else [],
                "lib": self.libInfo,
                "cfg": self._cfg,
                "dl": self._dl[-6:],
            }
            self._send_gui(init_data)
        except Exception as e:
            print(f"qt-music: send init error: {e}", file=sys.stderr)

    def _send_gui(self, data):
        if not self._gui_sock:
            return
        try:
            raw = (json.dumps(data, ensure_ascii=False) + "\n").encode("utf-8")
            self._gui_sock.setblocking(True)
            self._gui_sock.sendall(raw)
            self._gui_sock.setblocking(False)
        except Exception:
            self._close_gui_sock()

    def _on_gui_io(self, _fd, cond):
        if not self._gui_sock:
            return False
        if cond & _GLib.IOCondition.IN:
            try:
                chunk = self._gui_sock.recv(65536)
            except BlockingIOError:
                return True
            except Exception:
                self._on_gui_disconnected()
                return False
            if not chunk:
                self._on_gui_disconnected()
                return False
            self._gui_buf += chunk
            while b"\n" in self._gui_buf:
                line, self._gui_buf = self._gui_buf.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line.decode("utf-8", errors="replace"))
                    self._handle_gui_cmd(msg)
                except Exception:
                    pass
            if cond & (_GLib.IOCondition.HUP | _GLib.IOCondition.ERR):
                self._on_gui_disconnected()
                return False
            return True
        self._on_gui_disconnected()
        return False

    def _on_gui_disconnected(self):
        self._close_gui_sock()
        self._gui_proc = None
        self._restore_prev_desktop()
        _trim_heap()

    def _handle_gui_cmd(self, msg):
        cmd = msg.get("cmd")
        if cmd == "playPause": self.playPause()
        elif cmd == "next": self.next()
        elif cmd == "prev": self.prev()
        elif cmd == "seek": self.seek(msg.get("sec", 0.0))
        elif cmd == "volume": self.volume(msg.get("delta", 0.0))
        elif cmd == "reshuffle": self.reshuffle()
        elif cmd == "pick":
            self.pick(msg["kind"], msg["ident"], msg["queue_only"])
            self._send_gui({"type": "queue", "rows": self.own.queue_rows() if self.own else []})
        elif cmd == "pickOnline":
            self.pickOnline(msg["vid"], msg["queue_only"])
            self._send_gui({"type": "queue", "rows": self.own.queue_rows() if self.own else []})
        elif cmd == "queuePlay":
            self.queuePlay(msg["path"])
            self._send_gui({"type": "queue", "rows": self.own.queue_rows() if self.own else []})
        elif cmd == "queueRemove":
            self.queueRemove(msg["path"])
            self._send_gui({"type": "queue", "rows": self.own.queue_rows() if self.own else []})
        elif cmd == "queueMove":
            self.queueMove(msg["path"], msg["delta"])
            self._send_gui({"type": "queue", "rows": self.own.queue_rows() if self.own else []})
        elif cmd == "queueClear":
            self.queueClear()
            self._send_gui({"type": "queue", "rows": self.own.queue_rows() if self.own else []})
        elif cmd == "search": self.search(msg.get("query", ""), msg.get("kind", "songs"))
        elif cmd == "drillAlbum": self.drillAlbum(msg.get("browse_id", ""))
        elif cmd == "dlStart": self.dlStart(msg.get("vid", ""), msg.get("title", ""), msg.get("sub", ""))
        elif cmd == "dlLink": self.dlLink(msg.get("url", ""))
        elif cmd == "rescan": self.rescan()
        elif cmd == "adjustOffset":
            self.adjustOffset(msg.get("delta", 0.0))
            self._send_gui({"type": "offset", "offset": self._offset})
        elif cmd == "adjustSpread":
            self.adjustSpread(msg.get("delta", 0.0))
        elif cmd == "saveSetting": self.saveSetting(msg.get("key"), msg.get("val"))
        elif cmd == "hideWindow": self.hideWindow()
        elif cmd == "quitApp": self.quitApp()

    def hideWindow(self):
        if self._gui_sock:
            try:
                self._send_gui({"type": "close"})
            except Exception:
                pass
        self._close_gui_sock()
        proc = self._gui_proc
        self._gui_proc = None
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=0.25)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        self._restore_prev_desktop()
        _trim_heap()

    def showWindow(self):
        if self._gui_proc and self._gui_proc.poll() is None:
            self._post_show_desktop_5()
            return
        if not getattr(self.a, "windowed", False) and not getattr(self.a, "screenshot", None):
            self._capture_prev_desktop()
        cmd = [sys.executable, str(Path(__file__).resolve().with_name("qt-music")), "--gui-proc"]
        if getattr(self.a, "lite", False): cmd.append("--lite")
        if getattr(self.a, "windowed", False): cmd.append("--windowed")
        if getattr(self.a, "font", None): cmd.extend(["--font", self.a.font])
        if getattr(self.a, "music", None): cmd.extend(["--music", self.a.music])
        if getattr(self.a, "size", None): cmd.extend(["--size", self.a.size])
        if getattr(self.a, "keys", None): cmd.extend(["--keys", self.a.keys])
        if getattr(self.a, "screenshot", None): cmd.extend(["--screenshot", self.a.screenshot])
        self._gui_proc = subprocess.Popen(cmd)

    def toggleWindow(self):
        cur = ""
        try:
            cur = subprocess.check_output(["bspc", "query", "-D", "-d", "focused", "--names"], encoding="utf-8", timeout=0.35).strip()
        except Exception:
            pass
        if self._gui_proc and self._gui_proc.poll() is None:
            if not cur or cur == "5":
                self.hideWindow()
            else:
                self._prev_desktop = cur
                self._post_show_desktop_5()
        else:
            self.showWindow()

    def quitApp(self):
        try:
            self.hideWindow()
        except Exception:
            pass
        try:
            if self.own:
                self.own.deactivate()
        except Exception:
            pass
        try:
            fifo_path = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "polybar_music.fifo")
            if os.path.exists(fifo_path):
                fd = os.open(fifo_path, os.O_WRONLY | os.O_NONBLOCK)
                try:
                    os.write(fd, b"\n")
                finally:
                    os.close(fd)
        except Exception:
            pass
        for sp in getattr(self, "_socket_paths", []):
            try:
                os.unlink(sp)
            except FileNotFoundError:
                pass
            except Exception:
                pass
        if self._pid_file:
            try:
                os.unlink(self._pid_file)
            except Exception:
                pass
        if self._lock_fh:
            try:
                self._lock_fh.close()
            except Exception:
                pass
        if self._loop:
            try:
                self._loop.quit()
            except Exception:
                pass

    def volume(self, delta):
        if self.own:
            v = self.own.set_volume(self.own.vol + delta)
            self._save("volume", v)
            self.toast.emit(f"volume {round(v * 100)}%")
            self._send_gui({"type": "volume", "vol": v})

    # ---- worker thread -> UI thread
    def _on_meta(self, js):
        self._meta_d = json.loads(js)
        self.metaChanged.emit()
        self._send_gui({"type": "meta", "meta": self._meta_d})

    def _on_lyr(self, js):
        d = json.loads(js)
        self._kind, self._src, self._wordlevel = d["kind"], d.get("src", ""), bool(d.get("wordlevel"))
        self._raw, self._length = d.get("raw"), d.get("length") or 0.0
        self._lyr_json = json.dumps(d["lines"], ensure_ascii=False)
        self.lyricsChanged.emit()
        self._send_gui({"type": "lyrics", "data": d})

    def _on_art(self, js):
        self._art_d = json.loads(js)
        self.artChanged.emit()
        self._send_gui({"type": "art", "data": self._art_d})

    def _kill_follow(self):
        pass

    # ---- control methods called by IPC/MPRIS
    def playPause(self):
        if self.own:
            self.own.toggle()

    def next(self):
        if self.own:
            self.own.next()

    def prev(self):
        if self.own:
            self.own.prev()

    def seek(self, sec):
        if self.own:
            self.own.seek(sec)

    def adjustOffset(self, d):
        self._offset = round(max(-5.0, min(5.0, self._offset + d)), 2)
        try:
            OFFSET_FILE.parent.mkdir(parents=True, exist_ok=True)
            OFFSET_FILE.write_text(json.dumps({"offset": self._offset}))
        except OSError:
            pass
        self.tuneChanged.emit()
        self.toast.emit(f"lyric timing {self._offset:+.1f}s")

    def adjustSpread(self, d):
        qm_core.SPREAD = round(max(0.4, min(2.5, qm_core.SPREAD + d)), 2)
        if self._raw and self._kind == "synced":
            self._lyr_json = json.dumps(parse_lrc(self._raw, self._length), ensure_ascii=False)
            self.lyricsChanged.emit()
            self._send_gui({"type": "lyrics", "data": {
                "kind": self._kind, "lines": json.loads(self._lyr_json), "src": self._src,
                "wordlevel": self._wordlevel, "raw": self._raw, "length": self._length,
            }})
        self._send_gui({"type": "spread", "spread": qm_core.SPREAD})
        self.toast.emit(f"word spread ×{qm_core.SPREAD:.2f}  ( , shorter   . longer )")



def main_daemon(a, ipc_names):
    GLib, _Gio = _ensure_glib()
    uid = os.getuid()
    lock_path = f"/tmp/qt-music-{uid}.lock"
    pid_path = f"/tmp/qt-music-{uid}.pid"
    lock_fh = open(lock_path, "w")
    try:
        fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit(0)
    with open(pid_path, "w") as pf:
        pf.write(str(os.getpid()))

    bridge = Bridge(a)
    bridge._ipc_names = ipc_names
    bridge._pid_file = pid_path
    bridge._lock_fh = lock_fh
    loop = GLib.MainLoop()
    bridge._loop = loop

    sock_paths = []
    srv_socks = []

    def _handle_conn(conn):
        buf = b""
        conn.settimeout(0.5)
        try:
            while b"\n" not in buf:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buf += chunk
        except Exception:
            pass
        lines = [ln.strip() for ln in buf.decode("utf-8", errors="ignore").split("\n") if ln.strip()]
        if not lines:
            try:
                conn.close()
            except Exception:
                pass
            return
        for line in lines:
            if line == "toggle":
                bridge.toggleWindow()
                try:
                    conn.sendall(b"ok\n")
                    conn.close()
                except Exception:
                    pass
                return
            elif line == "show":
                bridge.showWindow()
                try:
                    conn.sendall(b"ok\n")
                    conn.close()
                except Exception:
                    pass
                return
            elif line == "hide":
                bridge.hideWindow()
                try:
                    conn.sendall(b"ok\n")
                    conn.close()
                except Exception:
                    pass
                return
            elif line == "quit":
                try:
                    conn.sendall(b"ok\n")
                    conn.close()
                except Exception:
                    pass
                GLib.idle_add(lambda: (bridge.quitApp(), False)[-1])
                return
            else:
                try:
                    msg = json.loads(line)
                    if msg.get("cmd") == "gui_connect":
                        bridge.set_gui_client(conn)
                        return
                    bridge._handle_gui_cmd(msg)
                except Exception:
                    pass
        try:
            conn.close()
        except Exception:
            pass

    def _on_accept(sock, _cond):
        try:
            conn, _ = sock.accept()
        except BlockingIOError:
            return True
        except Exception:
            return True
        _handle_conn(conn)
        return True

    for s_name in ipc_names:
        sp = "/tmp/" + s_name
        try:
            os.unlink(sp)
        except FileNotFoundError:
            pass
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(sp)
        srv.listen(8)
        srv.setblocking(False)
        srv_socks.append(srv)
        sock_paths.append(sp)
        GLib.io_add_watch(srv.fileno(), GLib.IOCondition.IN, lambda _fd, _c, s=srv: _on_accept(s, _c))

    bridge._socket_paths = sock_paths
    bridge.start()

    # Handle SIGTERM / SIGHUP / SIGINT cleanly on the GLib main loop
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        try:
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: (bridge.quitApp(), False)[-1])
        except Exception:
            pass

    if not a.tray:
        bridge.showWindow()

    _trim_heap()
    try:
        loop.run()
    finally:
        for srv in srv_socks:
            try:
                srv.close()
            except Exception:
                pass
        bridge.quitApp()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)


