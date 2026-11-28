#!/usr/bin/env python3
"""On-demand PySide6 QtQuick GUI client process for qt-music."""
from __future__ import annotations

import hashlib
import json
import os
os.environ.setdefault('QSG_RENDER_LOOP', 'basic')
import subprocess
import sys
import time
from pathlib import Path

import qm_core
from qm_core import CACHE, Library, online_available, parse_lrc, _normalize_settings, _uri_from_path

def _build_gui_runtime():
    """Import PySide6 QtGui/QtQuick ONLY inside --gui-proc (zero Qt overhead in daemon or CLI)."""
    try:
        from PySide6.QtCore import Property, QObject, Qt, QTimer, QUrl, Signal, Slot
        from PySide6.QtGui import QGuiApplication, QPixmapCache
        from PySide6.QtNetwork import QLocalSocket
        from PySide6.QtQml import QQmlApplicationEngine
        from PySide6.QtQuick import QQuickWindow  # noqa: F401
    except ImportError:
        sys.exit(
            "qt-music GUI needs PySide6 (Qt Quick), which isn't installed.\n\n"
            "  Arch / CachyOS / Manjaro:  sudo pacman -S pyside6 qt6-declarative python-mutagen python-gobject\n"
        )

    class GuiBridge(QObject):
        metaChanged = Signal()
        lyricsChanged = Signal()
        artChanged = Signal()
        tuneChanged = Signal()
        modeChanged = Signal()
        libChanged = Signal()
        volumeChanged = Signal()
        cfgChanged = Signal()
        sync = Signal(float, bool)
        toast = Signal(str)
        searchDone = Signal(str)
        thumbsReady = Signal()
        dlChanged = Signal(str)

        def __init__(self, a, ipc_name):
            super().__init__()
            self.a = a
            self.ipc_name = ipc_name
            self._win = None
            self.lib = Library(self.a.music or os.environ.get("MUSICD_DIR") or Path.home() / "Music")
            self._lib_loaded = False

            self._meta_d = {"active": False, "playing": False, "title": "", "artist": "", "album": "", "length": 0.0}
            self._kind, self._lyr_json, self._src, self._raw, self._length = "none", "[]", "", None, 0.0
            self._art_d = {"art": "", "bg": "", "c1": "#6c5ce7", "c2": "#00b894"}
            self._wordlevel = False
            self._offset = 0.0
            self._spread = 1.0
            self._vol = 0.8
            self._queue_rows = []
            self._lib_info = {"ready": True, "count": 0, "scanning": False, "dir": str(self.lib.root), "engineErr": "", "online": online_available()}

            self._set_file = CACHE / "settings.json"
            try:
                raw_s = json.loads(self._set_file.read_text())
            except Exception:
                raw_s = {}
            self._settings = _normalize_settings(raw_s)
            self._cfg = {"windowed": bool(self.a.windowed or self.a.screenshot), "lite": bool(self.a.lite), "controls": bool(self.a.controls),
                         "wstyle": int(self._settings.get("wstyle", 0)),
                         "font": self.a.font or os.environ.get("LYRICVIEW_FONT") or "",
                         **self._settings}

            self.sock = QLocalSocket(self)
            self._buf = b""
            self.sock.readyRead.connect(self._on_ready_read)
            self.sock.disconnected.connect(self._on_disconnected)
            for _ in range(30):
                for name in [self.ipc_name, f"qt-music-ipc-{os.getuid()}", f"lyricview-ipc-{os.getuid()}"]:
                    self.sock.connectToServer(name)
                    if self.sock.waitForConnected(40):
                        break
                if self.sock.state() == QLocalSocket.ConnectedState:
                    break
                time.sleep(0.03)
            self._send({"cmd": "gui_connect"})

        def _ensure_lib(self):
            if not self._lib_loaded:
                self._lib_loaded = True
                self.lib.load_cache()

        def _send(self, data):
            try:
                line = (json.dumps(data, ensure_ascii=False) + "\n").encode("utf-8")
                self.sock.write(line)
                self.sock.flush()
            except Exception:
                pass

        def _on_ready_read(self):
            self._buf += bytes(self.sock.readAll())
            while b"\n" in self._buf:
                line, self._buf = self._buf.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line.decode("utf-8", errors="replace"))
                    self._handle_msg(msg)
                except Exception:
                    pass

        def _on_disconnected(self):
            QGuiApplication.quit()

        def _handle_msg(self, msg):
            mtype = msg.get("type")
            if mtype == "init":
                self._meta_d = msg.get("meta", self._meta_d)
                self._art_d = msg.get("art", self._art_d)
                lyr = msg.get("lyrics", {})
                self._kind = lyr.get("kind", "none")
                self._src = lyr.get("src", "")
                self._wordlevel = bool(lyr.get("wordlevel", False))
                self._raw = lyr.get("raw")
                self._length = float(lyr.get("length") or 0.0)
                self._lyr_json = json.dumps(lyr.get("lines", []), ensure_ascii=False)
                self._offset = float(msg.get("offset", 0.0))
                self._spread = float(msg.get("spread", 1.0))
                self._vol = float(msg.get("volume", 0.8))
                self._queue_rows = msg.get("queue", [])
                self._lib_info = msg.get("lib", self._lib_info)
                if "cfg" in msg:
                    self._cfg.update(_normalize_settings(msg["cfg"]))
                    self.cfgChanged.emit()
                if "dl" in msg and msg["dl"]:
                    self.dlChanged.emit(json.dumps(msg["dl"], ensure_ascii=False))
                self.metaChanged.emit()
                self.artChanged.emit()
                self.lyricsChanged.emit()
                self.tuneChanged.emit()
                self.volumeChanged.emit()
                self.libChanged.emit()
                self.sync.emit(float(msg.get("pos", 0.0)), bool(msg.get("playing", False)))
            elif mtype == "close":
                QGuiApplication.quit()
            elif mtype == "sync":
                playing = bool(msg["playing"])
                if self._meta_d.get("playing") != playing:
                    self._meta_d = dict(self._meta_d, playing=playing)
                    self.metaChanged.emit()
                self.sync.emit(float(msg["pos"]), playing)
            elif mtype == "meta":
                self._meta_d = msg["meta"]
                self.metaChanged.emit()
            elif mtype == "lyrics":
                data = msg["data"]
                if isinstance(data, str):
                    data = json.loads(data)
                self._kind = data.get("kind", "none")
                self._src = data.get("src", "")
                self._wordlevel = bool(data.get("wordlevel", False))
                self._raw = data.get("raw")
                self._length = float(data.get("length") or 0.0)
                self._lyr_json = json.dumps(data.get("lines", []), ensure_ascii=False)
                self.lyricsChanged.emit()
            elif mtype == "art":
                data = msg["data"]
                if isinstance(data, str):
                    data = json.loads(data)
                self._art_d = data
                self.artChanged.emit()
            elif mtype == "status":
                self._meta_d = dict(self._meta_d, playing=bool(msg["playing"]))
                self.metaChanged.emit()
            elif mtype == "queue":
                self._queue_rows = msg["rows"]
            elif mtype == "toast":
                self.toast.emit(msg["msg"])
            elif mtype == "thumbsReady":
                self.thumbsReady.emit()
            elif mtype == "dlChanged":
                self.dlChanged.emit(msg["data"] if isinstance(msg["data"], str) else json.dumps(msg["data"], ensure_ascii=False))
            elif mtype == "libChanged":
                if self._lib_loaded:
                    self.lib.load_cache()
                self._lib_info = msg.get("info", self._lib_info)
                self.libChanged.emit()
            elif mtype == "searchDone":
                self.searchDone.emit(msg["data"] if isinstance(msg["data"], str) else json.dumps(msg["data"], ensure_ascii=False))
            elif mtype == "offset":
                self._offset = float(msg["offset"])
                self.tuneChanged.emit()
            elif mtype == "spread":
                self._spread = float(msg["spread"])
                self.tuneChanged.emit()
            elif mtype == "volume":
                self._vol = float(msg["vol"])
                self.volumeChanged.emit()

        # ---- properties read by QML
        @Property("QVariantMap", notify=metaChanged)
        def meta(self): return self._meta_d

        @Property("QVariantMap", notify=artChanged)
        def artInfo(self): return self._art_d

        @Property(str, notify=lyricsChanged)
        def lyrics(self): return self._lyr_json

        @Property(str, notify=lyricsChanged)
        def kind(self): return self._kind

        @Property(bool, notify=lyricsChanged)
        def wordLevel(self): return self._wordlevel

        @Property(bool, notify=metaChanged)
        def isStreaming(self): return bool(self._meta_d.get("key", "").startswith("yt"))

        @Property(float, notify=tuneChanged)
        def offset(self): return self._offset

        @Property(float, notify=tuneChanged)
        def spread(self): return self._spread

        @Property("QVariantMap", notify=cfgChanged)
        def cfg(self): return self._cfg

        @Property(str, notify=modeChanged)
        def mode(self): return "own"

        @Property(float, notify=volumeChanged)
        def vol(self): return self._vol

        @Property("QVariantMap", notify=libChanged)
        def libInfo(self): return self._lib_info

        def _thumb_path(self, a):
            return CACHE / "thumbs" / (hashlib.md5(f"{a['artist']}|{a['name']}".lower().encode()).hexdigest()[:16] + ".jpg")

        def _thumb_url(self, a):
            p = self._thumb_path(a)
            return _uri_from_path(p) if p.exists() else ""

        @Slot(str, result=str)
        def pickerData(self, spec):
            self._ensure_lib()
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
            else:
                if rest.startswith("album:") and int(rest[6:]) in lib.albums:
                    idxs = lib.albums[int(rest[6:])]["tracks"]
                else:
                    idxs = sorted(range(len(lib.tracks)), key=lambda i: (lib.tracks[i]["title"].lower(), lib.tracks[i]["artist"].lower()))
                rows = [{"id": i, "name": lib.tracks[i]["title"], "sub": f"{lib.tracks[i]['artist']} · {lib.tracks[i]['album']}", "n": 0,
                         "dur": f"{int(lib.tracks[i]['len'] // 60)}:{int(lib.tracks[i]['len'] % 60):02d}" if lib.tracks[i]["len"] else ""} for i in idxs]
            return json.dumps(rows, ensure_ascii=False)

        @Slot(result=str)
        def queueData(self):
            return json.dumps(self._queue_rows, ensure_ascii=False)

        @Slot()
        def playPause(self): self._send({"cmd": "playPause"})

        @Slot()
        def next(self): self._send({"cmd": "next"})

        @Slot()
        def prev(self): self._send({"cmd": "prev"})

        @Slot(float)
        def seek(self, sec): self._send({"cmd": "seek", "sec": float(sec)})

        @Slot(float)
        def volume(self, delta):
            self._vol = max(0.0, min(1.0, self._vol + delta))
            self.volumeChanged.emit()
            self._send({"cmd": "volume", "delta": float(delta)})

        @Slot()
        def reshuffle(self): self._send({"cmd": "reshuffle"})

        @Slot()
        def toggleMode(self): self.reshuffle()

        @Slot(str, int, bool)
        def pick(self, kind, ident, queue_only):
            self._send({"cmd": "pick", "kind": kind, "ident": ident, "queue_only": queue_only})

        @Slot(str, bool)
        def pickOnline(self, vid, queue_only):
            self._send({"cmd": "pickOnline", "vid": vid, "queue_only": queue_only})

        @Slot(str)
        def queuePlay(self, path): self._send({"cmd": "queuePlay", "path": path})

        @Slot(str)
        def queueRemove(self, path): self._send({"cmd": "queueRemove", "path": path})

        @Slot(str, int, result=bool)
        def queueMove(self, path, delta):
            self._send({"cmd": "queueMove", "path": path, "delta": delta})
            return True

        @Slot()
        def queueClear(self): self._send({"cmd": "queueClear"})

        @Slot(str, str)
        def search(self, query, kind="songs"):
            self._send({"cmd": "search", "query": query, "kind": kind})

        @Slot(str)
        def drillAlbum(self, browse_id):
            self._send({"cmd": "drillAlbum", "browse_id": browse_id})

        @Slot(str, str, str)
        def dlStart(self, vid, title, sub):
            self._send({"cmd": "dlStart", "vid": vid, "title": title, "sub": sub})

        @Slot(str)
        def dlLink(self, url):
            self._send({"cmd": "dlLink", "url": url})

        @Slot()
        def rescan(self): self._send({"cmd": "rescan"})

        @Slot(float)
        def adjustOffset(self, d):
            self._offset = round(max(-5.0, min(5.0, self._offset + d)), 2)
            self.tuneChanged.emit()
            self.toast.emit(f"lyric timing {self._offset:+.1f}s")
            self._send({"cmd": "adjustOffset", "delta": d, "offset": self._offset})

        @Slot(float)
        def adjustSpread(self, d):
            self._spread = round(max(0.4, min(2.5, self._spread + d)), 2)
            self.tuneChanged.emit()
            if self._raw and self._kind == "synced":
                qm_core.SPREAD = self._spread
                self._lyr_json = json.dumps(parse_lrc(self._raw, self._length), ensure_ascii=False)
                self.lyricsChanged.emit()
            self.toast.emit(f"word spread ×{self._spread:.2f}  ( , shorter   . longer )")
            self._send({"cmd": "adjustSpread", "delta": d})

        @Slot(str, "QVariant")
        def saveSetting(self, key, val):
            if hasattr(val, "toVariant"):
                val = val.toVariant()
            self._cfg[key] = val
            self.cfgChanged.emit()
            self._send({"cmd": "saveSetting", "key": key, "val": val})

        @Slot()
        def hideWindow(self):
            try:
                self._send({"cmd": "hideWindow"})
            except Exception:
                pass
            if self._win:
                try:
                    self._win.close()
                    self._win.destroy()
                except Exception:
                    pass
            QTimer.singleShot(10, QGuiApplication.quit)

        @Slot()
        def showWindow(self): pass

        @Slot()
        def toggleWindow(self): self.hideWindow()

        @Slot()
        def quitApp(self):
            try:
                self._send({"cmd": "quitApp"})
            except Exception:
                pass
            QTimer.singleShot(20, QGuiApplication.quit)

        @Slot(result=str)
        def getClipboard(self):
            try:
                return QGuiApplication.clipboard().text() or ""
            except Exception:
                return ""

        @Slot(str)
        def setClipboard(self, s):
            try:
                QGuiApplication.clipboard().setText(s)
            except Exception:
                pass

    return QGuiApplication, QPixmapCache, QQmlApplicationEngine, Qt, QTimer, QUrl, GuiBridge


VIDEO_BG_QML = r"""import QtQuick
import QtMultimedia

Item {
    anchors.fill: parent
    property string videoSource: ""
    property real bgDim: 0.65
    signal failed()
    VideoOutput {
        id: bgVideo
        anchors.fill: parent
        fillMode: VideoOutput.PreserveAspectCrop
        opacity: parent.bgDim
    }
    MediaPlayer {
        id: bgPlayer
        source: parent.videoSource
        loops: MediaPlayer.Infinite
        audioOutput: null
        videoOutput: bgVideo
        onErrorOccurred: (e, msg) => parent.failed()
        Component.onCompleted: if (source !== "") play()
    }
}
"""


QML = r"""
import QtQuick
import QtQuick.Window
import QtQuick.Layouts
import QtQuick.Shapes
import QtQuick.Effects

Window {
    id: win
    width: 1280; height: 720; color: "#050507"
    title: bridge.meta.title ? bridge.meta.artist + " – " + bridge.meta.title : "qt-music"
    visibility: bridge.cfg.windowed ? Window.Windowed : Window.FullScreen
    flags: Qt.Window

    onClosing: function(closeEvent) {
        closeEvent.accepted = false
        bridge.hideWindow()
    }

    component Icon: Item {
        id: ic
        property string d
        signal clicked()
        width: 56; height: 56
        Shape {
            anchors.centerIn: parent; width: 24; height: 24; scale: 1.25
            ShapePath { fillColor: Qt.rgba(1, 1, 1, 0.85); strokeWidth: -1; PathSvg { path: ic.d } }
        }
    }

    // two crossfading copies of the (pre-blurred) artwork
    component ArtLayer: Item {
        id: al
        property bool flip: false
        function setSource(u) {
            var show = flip ? b : a, hide = flip ? a : b
            flip = !flip
            show.source = u; show.opacity = 1; hide.opacity = 0
        }
        function clear() { a.opacity = 0; b.opacity = 0 }
        Image { id: a; anchors.fill: parent; smooth: true; asynchronous: true; opacity: 0; Behavior on opacity { NumberAnimation { duration: 1400 } } }
        Image { id: b; anchors.fill: parent; smooth: true; asynchronous: true; opacity: 0; Behavior on opacity { NumberAnimation { duration: 1400 } } }
    }

    // soft colour cloud that wanders across the window
    component Blob: Shape {
        id: bl
        property color col: "white"
        property real fx: 0.5          // home position (fraction of window)
        property real fy: 0.5
        property real size: 0.9        // diameter relative to the window's long side
        property int dur: 20000
        property real dx: 0
        property real dy: 0
        readonly property real d: Math.max(win.width, win.height) * size
        width: d; height: d
        x: win.width * fx - d / 2 + dx
        y: win.height * fy - d / 2 + dy
        SequentialAnimation on dx {
            loops: Animation.Infinite; running: !root.lite
            NumberAnimation { to: win.width * 0.20; duration: bl.dur; easing.type: Easing.InOutSine }
            NumberAnimation { to: -win.width * 0.20; duration: bl.dur; easing.type: Easing.InOutSine }
        }
        SequentialAnimation on dy {
            loops: Animation.Infinite; running: !root.lite
            NumberAnimation { to: -win.height * 0.22; duration: bl.dur * 1.37; easing.type: Easing.InOutSine }
            NumberAnimation { to: win.height * 0.22; duration: bl.dur * 1.37; easing.type: Easing.InOutSine }
        }
        ShapePath {
            strokeWidth: -1
            fillGradient: RadialGradient {
                centerX: bl.d / 2; centerY: bl.d / 2; centerRadius: bl.d / 2; focalX: bl.d / 2; focalY: bl.d / 2
                GradientStop { position: 0.0; color: Qt.rgba(bl.col.r, bl.col.g, bl.col.b, 0.85) }
                GradientStop { position: 0.55; color: Qt.rgba(bl.col.r, bl.col.g, bl.col.b, 0.28) }
                GradientStop { position: 1.0; color: Qt.rgba(bl.col.r, bl.col.g, bl.col.b, 0) }
            }
            PathSvg { path: "M0,0 L" + bl.d + ",0 L" + bl.d + "," + bl.d + " L0," + bl.d + " Z" }
        }
    }

    // the word being sung: dim base + 8 stacked clips -> a smooth gradient wipe, optional GPU glow
    component SoftWipe: Item {
        id: sw
        property string word
        property font fnt
        property real p: 0
        property real tw: 0
        property real h: 0
        property real edge: 20
        property real glow: 0
        width: tw; height: h
        layer.enabled: sw.glow > 0 && !root.lite
        layer.effect: MultiEffect { shadowEnabled: true; shadowColor: "white"; shadowOpacity: 0.55 * sw.glow; shadowBlur: 1.0; shadowScale: 1.0 }
        Repeater {
            model: 8
            delegate: Item {
                required property int index
                clip: true; height: sw.h
                width: Math.min(sw.tw, sw.tw * sw.p + sw.edge * (7 - index) / 8)
                visible: width > 0
                Text { text: sw.word; font: sw.fnt; color: Qt.rgba(1, 1, 1, 0.36) }
            }
        }
    }

    component GlowText: Item {
        id: gt
        property string text
        property font fnt
        property color col: "white"
        property real glow: 1
        width: m.implicitWidth; height: m.implicitHeight
        layer.enabled: gt.glow > 0 && !root.lite
        layer.effect: MultiEffect { shadowEnabled: true; shadowColor: gt.col; shadowOpacity: 0.75 * gt.glow; shadowBlur: 1.0 }
        Text { visible: gt.glow > 0 && root.lite; text: gt.text; font: gt.fnt; color: gt.col; opacity: 0.16 * gt.glow; scale: 1.1; anchors.centerIn: m }
        Text { visible: gt.glow > 0 && root.lite; text: gt.text; font: gt.fnt; color: gt.col; opacity: 0.09 * gt.glow; scale: 1.22; anchors.centerIn: m }
        Text { id: m; text: gt.text; font: gt.fnt; color: gt.col }
    }

    component RainDrop: Item {
        id: rd
        property string word
        property font fnt
        property real fall: 0
        property real after: 0
        property real cx: 0
        property real areaW: 600
        property real areaH: 600
        property real hit: 0.58
        property real tilt: 0
        width: gt2.width; height: gt2.height
        visible: (fall > 0 || after > 0) && opacity > 0.01
        x: Math.max(8, Math.min(areaW - width - 8, cx - width / 2))
        y: -height + fall * (0.4 + 0.6 * fall) * (areaH * hit + height) + after * areaH * 0.07
        rotation: tilt
        opacity: after > 0 ? 1 - after : (fall < 0.12 ? fall / 0.12 : 1)
        scale: after > 0 ? 1 + 0.22 * Math.sin(Math.min(1, after * 2.4) * Math.PI) : 0.88 + 0.12 * Math.min(1, fall * 3)
        GlowText { id: gt2; text: rd.word; fnt: rd.fnt; glow: rd.visible ? (rd.after > 0 ? 1 : 0.45 + 0.4 * rd.fall) : 0 }
        function go(t, size, xx, aw, ah, remMs) {
            seq.stop(); word = t; areaW = aw; areaH = ah; cx = xx; tilt = (Math.random() - 0.5) * 12
            fnt = Qt.font({ family: bridge.cfg.font ? bridge.cfg.font : Qt.application.font.family, pixelSize: Math.max(8, Math.round(size)), weight: Font.Black })
            fall = 0; after = 0; fallAnim.duration = Math.max(150, remMs); seq.start()
        }
        function halt() { seq.stop(); fall = 0; after = 0 }
        SequentialAnimation {
            id: seq
            NumberAnimation { id: fallAnim; target: rd; property: "fall"; from: 0; to: 1; easing.type: Easing.Linear }
            NumberAnimation { target: rd; property: "after"; from: 0; to: 1; duration: 650; easing.type: Easing.OutQuad }
        }
        Connections { target: root; function onPlayingChanged() { if (seq.running) seq.paused = !root.playing } }
    }

    Item {
        id: root
        anchors.fill: parent
        focus: true
        readonly property bool lite: bridge.cfg.lite || GraphicsInfo.api === GraphicsInfo.Software

        // ───── playback clock
        property var lines: []
        property real pos: 0
        property real basePos: 0
        property double baseT: Date.now()
        property string curKey: ""
        property bool playing: bridge.meta.playing === true
        readonly property real offset: bridge.offset
        readonly property real len: bridge.meta.length || 0
        readonly property bool atEnd: len > 0 && pos >= len
        readonly property real spreadVal: bridge.spread
        readonly property real vol: bridge.vol
        readonly property string kind: bridge.kind

        // ───── responsive layout: wide-short, normal and tall-narrow windows (scratchpads!)
        // Layout polish & progress styling
        property real coverTitleGap: (bridge.cfg.coverTitleGap !== undefined ? bridge.cfg.coverTitleGap : 14)
        property int progressStyle: (bridge.cfg.progressStyle !== undefined ? bridge.cfg.progressStyle : 2)
        property bool showProgress: (bridge.cfg.showProgress !== undefined ? bridge.cfg.showProgress : true)

        // Background & user media
        property string bgType: (typeof bridge.cfg.bgType === "string" && bridge.cfg.bgType !== "") ? bridge.cfg.bgType : "clouds" // clouds | backdrop | video | image | none
        property string userBgPath: bridge.cfg.userBgPath || ""
        property real bgDim: (bridge.cfg.bgDim !== undefined && Number(bridge.cfg.bgDim) > 0.05) ? Number(bridge.cfg.bgDim) : 0.65
        property bool bgVideoError: false
        property string videoQmlUrl: ""

        // Element toggles & Clean View
        property bool cleanView: false
        property bool elemShowLyrics: (bridge.cfg.elemShowLyrics !== undefined ? bridge.cfg.elemShowLyrics : true)
        property bool elemShowCover: (bridge.cfg.elemShowCover !== undefined ? bridge.cfg.elemShowCover : true)
        property bool elemShowTitle: (bridge.cfg.elemShowTitle !== undefined ? bridge.cfg.elemShowTitle : true)
        property bool elemShowProgress: (bridge.cfg.elemShowProgress !== undefined ? bridge.cfg.elemShowProgress : true)
        property bool elemShowBgLayers: (bridge.cfg.elemShowBgLayers !== undefined ? bridge.cfg.elemShowBgLayers : true)
        property bool elemShowToasts: (bridge.cfg.elemShowToasts !== undefined ? bridge.cfg.elemShowToasts : true)

        // Unified Get Music tab
        property string getMusicTab: "songs" // songs | albums
        property string albumDrillBrowseId: ""
        property string albumDrillTitle: ""

        // Settings Overlay navigation
        property int setTab: 0 // 0: Display, 1: Audio, 2: Background, 3: Keybinds
        property int setSel: 0
        property bool keyListening: false
        property int listeningActionIdx: -1
        readonly property var actionSpecs: [
            { id: "playPause", label: "Play / Pause", def: "Space", desc: "Play / Pause" },
            { id: "next", label: "Next Track", def: "N", desc: "Next Song" },
            { id: "prev", label: "Prev Track", def: "P", desc: "Previous Song" },
            { id: "seekFwd", label: "Seek Forward (+5s)", def: "Right", desc: "Seek +5s (Shift: +30s)" },
            { id: "seekBack", label: "Seek Back (-5s)", def: "Left", desc: "Seek -5s (Shift: -30s)" },
            { id: "getMusic", label: "Get Music (Stream & DL)", def: "S", desc: "Get Music (YouTube Music preview & queue)" },
            { id: "pick", label: "Library Picker", def: "Tab", desc: "Music Library (Albums · Artists · Songs)" },
            { id: "queue", label: "Queue Overlay", def: "Q", desc: "Up Next (Queue)" },
            { id: "reshuffle", label: "Play / Reshuffle (Exit stream)", def: "M", desc: "Play / Reshuffle Library (Exit streaming)" },
            { id: "wordMode", label: "Word Mode", def: "W", desc: "Word Mode (Stack · Edit · Rain)" },
            { id: "wordStyle", label: "Word Style", def: "T", desc: "Cycle Word Style" },
            { id: "backdrop", label: "Backdrop Mode", def: "B", desc: "Backdrop Mode (blurred cover & wide lyrics)" },
            { id: "settings", label: "Settings", def: "O", desc: "Settings (Display, Audio, Video, Keys)" },
            { id: "cleanView", label: "Clean Video View", def: "V", desc: "Clean View (focus on background/video)" },
            { id: "fullscreen", label: "Fullscreen", def: "F", desc: "Toggle Fullscreen" },
            { id: "quitApp", label: "Quit App", def: "Ctrl+Q", desc: "Quit" }
        ]
        property var customKeys: Object.assign({}, bridge.cfg.keybinds || {})
        function keyFor(actId) {
            if (customKeys && customKeys[actId]) return String(customKeys[actId])
            for (var i = 0; i < actionSpecs.length; i++) if (actionSpecs[i].id === actId) return actionSpecs[i].def
            return ""
        }
        function eventKeyStr(e) {
            var k = e.key
            var mods = []
            if ((e.modifiers & Qt.ControlModifier) !== 0 && k !== Qt.Key_Control) mods.push("Ctrl")
            if ((e.modifiers & Qt.ShiftModifier) !== 0 && k !== Qt.Key_Shift && e.text.length !== 1) mods.push("Shift")
            if ((e.modifiers & Qt.AltModifier) !== 0 && k !== Qt.Key_Alt) mods.push("Alt")
            var name = ""
            if (k === Qt.Key_Space) name = "Space"
            else if (k === Qt.Key_Return || k === Qt.Key_Enter) name = "Enter"
            else if (k === Qt.Key_Tab) name = "Tab"
            else if (k === Qt.Key_Backtab) name = "Tab"
            else if (k === Qt.Key_Escape) name = "Esc"
            else if (k === Qt.Key_Left) name = "Left"
            else if (k === Qt.Key_Right) name = "Right"
            else if (k === Qt.Key_Up) name = "Up"
            else if (k === Qt.Key_Down) name = "Down"
            else if (k === Qt.Key_BracketLeft) name = "["
            else if (k === Qt.Key_BracketRight) name = "]"
            else if (k === Qt.Key_Comma) name = ","
            else if (k === Qt.Key_Period) name = "."
            else if (k >= Qt.Key_F1 && k <= Qt.Key_F12) name = "F" + (k - Qt.Key_F1 + 1)
            else if (k >= Qt.Key_A && k <= Qt.Key_Z) name = String.fromCharCode(k)
            else if (k >= Qt.Key_0 && k <= Qt.Key_9) name = String.fromCharCode(k)
            else if (e.text && e.text.length === 1 && e.text.charCodeAt(0) >= 32) name = e.text.toUpperCase()
            if (name === "") return ""
            return mods.length ? mods.join("+") + "+" + name : name
        }
        function buildKeymap() {
            var out = [
                [keyFor("playPause"), "Play / Pause"],
                [keyFor("seekBack") + " / " + keyFor("seekFwd"), "Seek 5s (Shift: 30s)"],
                ["↑ / ↓", "Volume ±5%"],
                [keyFor("next") + " / " + keyFor("prev"), "Next / Previous Song"],
                [keyFor("pick"), "Music Library (Albums · Artists · Songs)"],
                [keyFor("getMusic"), "Get Music (YouTube Music preview & queue)"],
                [keyFor("queue"), "Up Next (Queue)"],
                [keyFor("reshuffle"), "Play / Reshuffle Library (Exit streaming)"],
                [keyFor("wordMode"), "Word Mode (Stack · Edit · Rain)"],
                [keyFor("wordStyle"), "Cycle Word Style"],
                [keyFor("backdrop"), "Backdrop Mode (blurred cover & wide lyrics)"],
                [keyFor("settings"), "Settings (Display, Audio, Video, Keys)"],
                [keyFor("cleanView"), "Clean View (focus on background/video)"],
                ["[ / ]", "Lyric Timing Offset ±100ms"],
                [", / .", "Word Timing Spread shorter / longer"],
                [keyFor("fullscreen"), "Toggle Fullscreen"],
                ["Ctrl+R", "Rescan Music Folder"],
                ["Esc", "Hide Window / Close Menu"],
                [keyFor("quitApp"), "Quit App"],
                ["F1", "Close / Open This Sheet"]
            ]
            return out
        }
        property var keymap: buildKeymap()
        readonly property bool portrait: win.width < win.height * 1.1
        readonly property real pad: Math.round(Math.min(win.width, win.height) * 0.05)
        readonly property real u: Math.min(win.height, win.width * 0.75)           // text unit
        readonly property real sideW: portrait ? win.width - 2 * pad : Math.min(win.width * 0.34, win.height * 0.80)
        readonly property real cardS: portrait ? Math.round(Math.min(win.width * 0.30, win.height * 0.20))
                                               : Math.round(Math.min(sideW, win.height * 0.5))
        readonly property real fs: Math.round(Math.max(18, Math.min(lv.width * 0.062, lv.height * 0.10, win.height * 0.062)))
        readonly property font lyricFont: Qt.font({ family: bridge.cfg.font ? bridge.cfg.font : Qt.application.font.family,
                                                    pixelSize: fs, weight: Font.ExtraBold })

        property color c1: "#6c5ce7"
        property color c2: "#00b894"
        readonly property color c3: Qt.hsla((c1.hslHue + 0.14) % 1, Math.min(1, c1.hslSaturation + 0.1), Math.min(0.62, c1.hslLightness + 0.06), 1)
        Behavior on c1 { ColorAnimation { duration: 1400 } }
        Behavior on c2 { ColorAnimation { duration: 1400 } }
        property bool idle: false

        // ───── keyboard-only overlays (picker / queue / search / download / keybinds), word mode, backdrop
        property string overlay: ""
        property string pickKind: "albums"
        property string drillSpec: ""
        property string drillLabel: ""
        property string filter: ""
        property int sel: 0
        property var items: []
        property var shown: []
        property var qOpen: ({})
        property var dlJobs: []
        property string searchNote: ""
        property bool wordMode: false
        property int wordStyle: Math.min(2, bridge.cfg.wstyle)
        readonly property var styleNames: ["Stack", "Edit", "Rain"]
        property bool backdrop: false
        property bool controlsOn: bridge.cfg.controls
        property var flat: []
        property real pulse: 0
        property int gridCols: 4
        property bool isGrid: overlay === "pick" && pickKind !== "songs"

        function say(t) { toastText.text = t; toast.opacity = 1; toastTimer.restart() }
        function punch() { pulseAnim.restart() }
        function buildFlat(lines) {
            var f = []
            for (var i = 0; i < lines.length; i++) {
                var L = lines[i]
                if (L.gap || !L.words) continue
                for (var k = 0; k < L.words.length; k++) {
                    var w = L.words[k], t = w.w.trim()
                    if (t !== "") {
                        var cleanText = t.replace(/[\(\)\[\]\{\}]/g, "").trim()
                        if (cleanText === "") cleanText = t
                        f.push({ t: w.t, e: w.e, w: cleanText, orig: t, line: i, k: k, n: L.words.length })
                    }
                }
            }
            return f
        }
        function flatIdx(p) {
            var a = flat, lo = 0, hi = a.length - 1, r = -1
            while (lo <= hi) { var m = (lo + hi) >> 1; if (a[m].t <= p) { r = m; lo = m + 1 } else hi = m - 1 }
            return r
        }
        function loadPick() { items = JSON.parse(bridge.pickerData(drillSpec !== "" ? drillSpec : pickKind)); shown = items }
        function openPick(kind, spec, label) {
            overlay = "pick"; pickKind = kind; drillSpec = spec || ""; drillLabel = label || ""; filter = ""; sel = 0
            loadPick()
        }
        function reloadQueue() {
            var a = JSON.parse(bridge.queueData()), rows = []
            for (var i = 0; i < a.length; i++) {
                var e = a[i], g = e.group === true, open = g && qOpen[i] === true
                rows.push({ name: e.name, sub: e.sub, group: g, n: e.n || 0, path: [i], depth: 0, open: open })
                if (open) for (var j = 0; j < e.kids.length; j++)
                    rows.push({ name: e.kids[j].name, sub: e.kids[j].sub, group: false, n: 0, path: [i, j], depth: 1, open: false })
            }
            items = rows; shown = rows; sel = Math.max(0, Math.min(sel, rows.length - 1))
        }
        function selectPath(p) {
            for (var k = 0; k < shown.length; k++) {
                var q = shown[k].path
                if (q.length === p.length && q[0] === p[0] && (p.length === 1 || q[1] === p[1])) { sel = k; return }
            }
        }
        function openOverlay(kind) {
            if (kind === "pick") { openPick("albums"); return }
            if (kind === "search" || kind === "download") kind = "get-music"
            overlay = kind; filter = ""; sel = 0; searchNote = ""; items = []; shown = []
            albumDrillBrowseId = ""; albumDrillTitle = ""
            if (kind === "queue") reloadQueue()
            if (kind === "get-music" && filter.length >= 2) typed()
        }
        function closeOverlay() { overlay = "" }
        function refilter() {
            var q = filter.toLowerCase().split(/\s+/).filter(function (x) { return x.length })
            if (q.length === 0) shown = items
            else shown = items.filter(function (it) {
                var h = (it.name + " " + (it.sub || "")).toLowerCase()
                for (var i = 0; i < q.length; i++) if (h.indexOf(q[i]) < 0) return false
                return true
            })
            sel = 0
        }
        function typed() {
            if ((overlay === "get-music" || overlay === "search" || overlay === "download") && albumDrillBrowseId === "") {
                if (filter.length < 2) { items = []; shown = []; searchNote = "" }
                else { searchNote = "searching…"; searchTimer.restart() }
            } else refilter()
        }
        function activate(queueOnly) {
            if ((overlay === "get-music" || overlay === "download") && filter.indexOf("http") === 0 && (!shown.length || filter.length > 20)) {
                bridge.dlLink(filter); filter = ""; items = []; shown = []; say("downloading link…"); return
            }
            if (!shown.length) return
            var it = shown[sel]
            if (overlay === "queue") { bridge.queuePlay(JSON.stringify(it.path)); closeOverlay(); return }
            if (overlay === "download") { bridge.dlStart(it.id, it.name, it.sub); say("downloading · " + it.name); return }
            if (overlay === "search") bridge.pickOnline(it.id, queueOnly)
            else if (overlay === "get-music") {
                if (getMusicTab === "albums" && albumDrillBrowseId === "") {
                    albumDrillBrowseId = it.id
                    albumDrillTitle = it.name
                    searchNote = "loading album tracks…"
                    bridge.drillAlbum(it.id)
                    return
                }
                bridge.pickOnline(it.id, queueOnly)
            }
            else bridge.pick(pickKind, it.id, queueOnly)
            if (!queueOnly) closeOverlay()
        }
        function drillIn() {
            if (!shown.length) return
            var it = shown[sel]
            if (pickKind === "artists") openPick("albums", "albums:artist:" + it.id, it.name)
            else if (pickKind === "albums") openPick("songs", "songs:album:" + it.id, it.name)
        }
        function drillOut() {
            if (drillSpec.indexOf("songs:album:") === 0) openPick("albums")
            else if (drillSpec.indexOf("albums:artist:") === 0) openPick("artists")
        }
        function moveSel(d) { sel = Math.max(0, Math.min(Math.max(0, shown.length - 1), sel + d)) }
        function overlayKey(e, ctrl, shift) {
            var k = e.key, it = shown.length ? shown[sel] : null
            if (overlay === "settings") {
                if (keyListening) {
                    if (k === Qt.Key_Escape) {
                        keyListening = false; say("remap cancelled"); return
                    }
                    if (k === Qt.Key_Control || k === Qt.Key_Shift || k === Qt.Key_Alt || k === Qt.Key_Meta) return
                    var spec = actionSpecs[listeningActionIdx]
                    if (!spec) { keyListening = false; return }
                    var kname = eventKeyStr(e)
                    if (kname !== "") {
                        var nk = Object.assign({}, customKeys)
                        // Remove conflicting binding if another action held the same key
                        for (var ai = 0; ai < actionSpecs.length; ai++) {
                            var aid = actionSpecs[ai].id
                            if (aid !== spec.id && keyFor(aid) === kname) {
                                say("reassigned " + kname + " from " + actionSpecs[ai].label + " to " + spec.label)
                                delete nk[aid]
                            }
                        }
                        nk[spec.id] = kname
                        customKeys = nk
                        keyListening = false
                        bridge.saveSetting("keybinds", nk)
                        keymap = buildKeymap()
                        say(spec.label + " bound to " + kname)
                    }
                    return
                }
                if (k === Qt.Key_Escape) { closeOverlay(); return }
                if (k === Qt.Key_Tab || k === Qt.Key_Backtab) {
                    setTab = (setTab + (k === Qt.Key_Backtab ? 3 : 1)) % 4
                    setSel = 0
                    return
                }
                if (k === Qt.Key_Up) { setSel = Math.max(0, setSel - 1); return }
                if (k === Qt.Key_Down) { setSel = Math.min(Math.max(0, setList.count - 1), setSel + 1); return }
                if (k === Qt.Key_Delete || k === Qt.Key_Backspace) {
                    if (setTab === 3 && actionSpecs[setSel]) {
                        var nk2 = Object.assign({}, customKeys)
                        delete nk2[actionSpecs[setSel].id]
                        customKeys = nk2
                        bridge.saveSetting("keybinds", nk2)
                        keymap = buildKeymap()
                        say("reset " + actionSpecs[setSel].label + " to " + actionSpecs[setSel].def)
                    }
                    return
                }
                if (k === Qt.Key_Left || k === Qt.Key_Right) {
                    var d = (k === Qt.Key_Right ? 1 : -1)
                    if (setTab === 0) { // Display
                        if (setSel === 0) { wordStyle = (wordStyle + (d > 0 ? 1 : 2)) % 3; bridge.saveSetting("wstyle", wordStyle); say("Word style: " + styleNames[wordStyle]) }
                        else if (setSel === 1) { progressStyle = (progressStyle + (d > 0 ? 1 : 2)) % 3; bridge.saveSetting("progressStyle", progressStyle); say("Progress style: " + ["Glow Line", "Dot Pill", "Waveform"][progressStyle]) }
                        else if (setSel === 2) { coverTitleGap = Math.max(0, Math.min(40, coverTitleGap + d * 4)); bridge.saveSetting("coverTitleGap", coverTitleGap); say("Cover spacing: " + coverTitleGap + "px") }
                        else if (setSel === 3) { elemShowProgress = !elemShowProgress; bridge.saveSetting("elemShowProgress", elemShowProgress); say("Show progress: " + elemShowProgress) }
                    } else if (setTab === 1) { // Audio & Library
                        if (setSel === 0) { bridge.volume(d * 0.05); say("Volume: " + Math.round(bridge.vol * 100) + "%") }
                        else if (setSel === 1) { bridge.adjustOffset(d * 0.1) }
                        else if (setSel === 2) { bridge.adjustSpread(d * 0.1) }
                    } else if (setTab === 2) { // Background & Media
                        if (setSel === 0) {
                            var btypes = ["clouds", "backdrop", "video", "image", "none"]
                            var curIdx = Math.max(0, btypes.indexOf(bgType))
                            var bidx = (curIdx + (d > 0 ? 1 : 4)) % 5
                            bgType = btypes[bidx]; bgVideoError = false; bridge.saveSetting("bgType", bgType); say("Background: " + bgType)
                        } else if (setSel === 1) {
                            bgDim = Math.max(0.1, Math.min(1.0, Math.round((bgDim + d * 0.05) * 100) / 100))
                            bridge.saveSetting("bgDim", bgDim); say("Background dim: " + Math.round(bgDim * 100) + "%")
                        } else if (setSel === 2) { elemShowLyrics = !elemShowLyrics; bridge.saveSetting("elemShowLyrics", elemShowLyrics); say("Show lyrics: " + elemShowLyrics) }
                        else if (setSel === 3) { elemShowCover = !elemShowCover; bridge.saveSetting("elemShowCover", elemShowCover); say("Show cover: " + elemShowCover) }
                        else if (setSel === 4) { elemShowTitle = !elemShowTitle; bridge.saveSetting("elemShowTitle", elemShowTitle); say("Show title: " + elemShowTitle) }
                    }
                    return
                }
                if (k === Qt.Key_Return || k === Qt.Key_Enter) {
                    if (setTab === 1 && setSel === 3) { bridge.reshuffle(); closeOverlay(); return }
                    if (setTab === 1 && setSel === 4) { bridge.rescan(); closeOverlay(); return }
                    if (setTab === 2 && setSel === 5) { cleanView = !cleanView; say(cleanView ? "clean view enabled" : "clean view disabled"); closeOverlay(); return }
                    if (setTab === 3) { keyListening = true; listeningActionIdx = setSel; say("Press new key (Esc cancel, Del reset)…"); return }
                }
                return
            }
            if (ctrl && k === Qt.Key_V || (shift && k === Qt.Key_Insert)) {
                filter += bridge.getClipboard(); typed(); return
            }
            if (ctrl && k === Qt.Key_C) {
                bridge.setClipboard(filter); say("copied query to clipboard"); return
            }
            if (ctrl && k === Qt.Key_X) {
                bridge.setClipboard(filter); filter = ""; typed(); say("cut to clipboard"); return
            }
            if (overlay === "get-music") {
                if (ctrl && (k === Qt.Key_D)) {
                    if (getMusicTab === "albums" && albumDrillBrowseId === "") {
                        say("press Enter on album first to pick or download tracks")
                        return
                    }
                    if (it && it.id) {
                        bridge.dlStart(it.id, it.name, it.sub)
                        say("downloading · " + it.name)
                    }
                    return
                }
                if (k === Qt.Key_Tab || k === Qt.Key_Backtab) {
                    getMusicTab = (getMusicTab === "songs" ? "albums" : "songs")
                    albumDrillBrowseId = ""; albumDrillTitle = ""
                    if (filter.trim().length >= 2) {
                        searchNote = "searching " + getMusicTab + "…"
                        searchTimer.restart()
                    } else {
                        items = []; shown = []; searchNote = ""
                    }
                    return
                }

                if (k === Qt.Key_Backspace && filter === "" && albumDrillBrowseId !== "") {
                    albumDrillBrowseId = ""; albumDrillTitle = ""
                    if (filter.trim().length >= 2) {
                        searchNote = "searching albums…"
                        searchTimer.restart()
                    } else {
                        items = []; shown = []; searchNote = ""
                    }
                    return
                }
            }
            var k = e.key, it = shown.length ? shown[sel] : null
            if (overlay === "help" || k === Qt.Key_Escape) { closeOverlay(); return }
            if (overlay === "queue") {
                if (shift && (k === Qt.Key_Up || k === Qt.Key_Down) && it) {
                    var d = k === Qt.Key_Up ? -1 : 1, np = it.path.slice()
                    if (bridge.queueMove(JSON.stringify(it.path), d)) {
                        np[np.length - 1] += d
                        if (it.depth === 0) { var a0 = qOpen[it.path[0]], b0 = qOpen[np[0]]; qOpen[it.path[0]] = b0; qOpen[np[0]] = a0 }
                        reloadQueue(); selectPath(np)
                    }
                    return
                }
                if (k === Qt.Key_Right && it && it.group) { qOpen[it.path[0]] = true; reloadQueue(); return }
                if (k === Qt.Key_Left && it) { var i0 = it.path[0]; if (qOpen[i0]) { qOpen[i0] = false; reloadQueue(); selectPath([i0]) } return }
                if (k === Qt.Key_Delete || k === Qt.Key_Backspace) {
                    if (shift) { bridge.queueClear(); qOpen = ({}); reloadQueue() }
                    else if (it) { bridge.queueRemove(JSON.stringify(it.path)); qOpen = ({}); reloadQueue() }
                    return
                }
            }
            if (k === Qt.Key_Down) { moveSel(isGrid ? gridCols : 1); return }
            if (k === Qt.Key_Up) { moveSel(isGrid ? -gridCols : -1); return }
            if (isGrid && k === Qt.Key_Right && !ctrl) { moveSel(1); return }
            if (isGrid && k === Qt.Key_Left && !ctrl) { moveSel(-1); return }
            if (k === Qt.Key_PageDown) { moveSel(8); return }
            if (k === Qt.Key_PageUp) { moveSel(-8); return }
            if (k === Qt.Key_Return || k === Qt.Key_Enter) { activate(shift); return }
            if (overlay === "pick") {
                if (ctrl && k === Qt.Key_Right) { drillIn(); return }
                if (ctrl && k === Qt.Key_Left) { drillOut(); return }
                if (k === Qt.Key_Tab || k === Qt.Key_Backtab) {
                    var order = ["albums", "artists", "songs"], n = (order.indexOf(pickKind) + (k === Qt.Key_Backtab ? 2 : 1)) % 3
                    openPick(order[n]); return
                }
                if (k === Qt.Key_Backspace && filter === "" && drillSpec !== "") { drillOut(); return }
            }
            if (overlay === "queue") return
            if (k === Qt.Key_Tab || k === Qt.Key_Backtab) return
            if (k === Qt.Key_Backspace) { filter = filter.slice(0, -1); typed(); return }
            if (e.text && e.text.length === 1 && e.text.charCodeAt(0) >= 32 && !ctrl) { filter += e.text; typed(); return }
            return
        }
        function runAction(act) {
            if (act === "playPause") bridge.playPause()
            else if (act === "next") bridge.next()
            else if (act === "prev") bridge.prev()
            else if (act === "seekFwd") seekTo(pos + 5)
            else if (act === "seekBack") seekTo(pos - 5)
            else if (act === "getMusic") openOverlay("get-music")
            else if (act === "pick") openOverlay("pick")
            else if (act === "queue") openOverlay("queue")
            else if (act === "reshuffle") bridge.reshuffle()
            else if (act === "wordMode") {
                wordMode = !wordMode
                if (!wordMode) say("full lyrics")
                else if (kind !== "synced") say("word mode needs synced lyrics - this song has none yet")
                else if (!bridge.wordLevel) say("⚠ these lyrics aren't word-by-word - word timing is estimated")
                else say("one word at a time · " + styleNames[wordStyle] + "  (T: style)")
            } else if (act === "wordStyle") {
                wordStyle = (wordStyle + 1) % 3; bridge.saveSetting("wstyle", wordStyle)
                say("style: " + styleNames[wordStyle] + (wordMode ? "" : "  (shows in word mode - press W)"))
            } else if (act === "backdrop") {
                backdrop = !backdrop; say(backdrop ? "cover backdrop · lyrics focus" : "normal view")
            } else if (act === "settings") openOverlay("settings")
            else if (act === "cleanView") {
                cleanView = !cleanView
                say(cleanView ? "clean view · video mode (press V to restore)" : "normal view")
            } else if (act === "fullscreen") {
                win.visibility = (win.visibility === Window.FullScreen ? Window.Windowed : Window.FullScreen)
            } else if (act === "quitApp") {
                bridge.quitApp()
            }
        }
        function onKey(e) {
            var ctrl = (e.modifiers & Qt.ControlModifier) !== 0, shift = (e.modifiers & Qt.ShiftModifier) !== 0
            if (e.key === Qt.Key_F1) { if (overlay === "help") closeOverlay(); else openOverlay("help"); wake(); return }
            if (overlay !== "") { overlayKey(e, ctrl, shift); wake(); return }
            if (shift && e.key === Qt.Key_Right) { seekTo(pos + 30); wake(); return }
            if (shift && e.key === Qt.Key_Left) { seekTo(pos - 30); wake(); return }
            if (shift && e.key === Qt.Key_T) {
                wordStyle = (wordStyle + 2) % 3; bridge.saveSetting("wstyle", wordStyle)
                say("style: " + styleNames[wordStyle]); wake(); return
            }
            var ks = eventKeyStr(e)
            if (ks !== "") {
                for (var ai = 0; ai < actionSpecs.length; ai++) {
                    if (keyFor(actionSpecs[ai].id) === ks) {
                        runAction(actionSpecs[ai].id); wake(); return
                    }
                }
            }
            switch (e.key) {
            case Qt.Key_Up: bridge.volume(0.05); break
            case Qt.Key_Down: bridge.volume(-0.05); break
            case Qt.Key_D: openOverlay("get-music"); break
            case Qt.Key_R: if (ctrl) bridge.rescan(); break
            case Qt.Key_C: controlsOn = !controlsOn; break
            case Qt.Key_BracketLeft: bridge.adjustOffset(-0.1); break
            case Qt.Key_BracketRight: bridge.adjustOffset(0.1); break
            case Qt.Key_Comma: bridge.adjustSpread(-0.1); break
            case Qt.Key_Period: bridge.adjustSpread(0.1); break
            case Qt.Key_Escape: bridge.hideWindow(); break
            }
            wake()
        }

        function findIdx(p) {
            var a = lines, lo = 0, hi = a.length - 1, r = -1
            while (lo <= hi) { var m = (lo + hi) >> 1; if (a[m].t <= p) { r = m; lo = m + 1 } else hi = m - 1 }
            return r
        }
        readonly property int activeIdx: kind === "synced" ? findIdx(pos + offset) : -1
        onActiveIdxChanged: if (!wordMode) punch()
        function fmt(s) { s = Math.max(0, Math.floor(s)); return Math.floor(s / 60) + ":" + ("0" + (s % 60)).slice(-2) }
        function seekTo(sec) { sec = Math.max(0, sec); basePos = sec; baseT = Date.now(); pos = sec; bridge.seek(sec) }
        function wake() { idle = false; idleTimer.restart() }

        Timer { id: searchTimer; interval: 450; onTriggered: if (root.overlay === "get-music" || root.overlay === "search" || root.overlay === "download") { if (root.filter.trim().length >= 2) bridge.search(root.filter.trim(), root.getMusicTab) } }
        NumberAnimation { id: pulseAnim; target: root; property: "pulse"; from: 1; to: 0; duration: 800; easing.type: Easing.OutCubic }
        Timer { id: idleTimer; interval: 3000; running: true; onTriggered: root.idle = true }
        FrameAnimation {
            running: root.playing && !root.atEnd
            onTriggered: {
                var p = root.basePos + (Date.now() - root.baseT) / 1000
                root.pos = root.len > 0 ? Math.min(p, root.len) : p
            }
        }

        Connections {
            target: bridge
            function onLyricsChanged() {
                root.lines = (bridge.kind === "synced" || bridge.kind === "plain") ? JSON.parse(bridge.lyrics) : []
                root.flat = bridge.kind === "synced" ? root.buildFlat(root.lines) : []
            }
            function onThumbsReady() { if (root.overlay === "pick" && root.pickKind !== "songs") { var s0 = root.sel; root.loadPick(); root.sel = s0 } }
            function onDlChanged(js) { root.dlJobs = JSON.parse(js) }
            function onSync(p, playing) {
                if (root.len > 0 && p > root.len) p = root.len
                var cur = root.playing ? root.basePos + (Date.now() - root.baseT) / 1000 : root.basePos
                if (playing !== root.playing || Math.abs(p - cur) > 0.25) {
                    root.basePos = p; root.baseT = Date.now(); root.pos = p
                }
            }
            function onMetaChanged() {
                var k = bridge.meta.key || ""
                if (k !== root.curKey) {            // new track: restart the clock at once, don't wait for the next sync
                    root.curKey = k
                    root.basePos = 0; root.baseT = Date.now(); root.pos = 0
                }
                if (!bridge.meta.active) { artA.clear(); artB.clear() }
            }
            function onArtChanged() {
                artA.setSource(bridge.artInfo.bg); artB.setSource(bridge.artInfo.bg)
                root.c1 = bridge.artInfo.c1; root.c2 = bridge.artInfo.c2
            }
            function onSearchDone(js) {
                var d = JSON.parse(js)
                if (root.overlay !== "search" && root.overlay !== "download" && root.overlay !== "get-music") return
                root.items = d.rows; root.shown = d.rows; root.sel = 0
                root.searchNote = d.error !== "" ? d.error : d.rows.length === 0 ? "nothing found" : ""
            }
            function onCfgChanged() {
                if (typeof bridge.cfg.bgType === "string" && bridge.cfg.bgType !== "") root.bgType = bridge.cfg.bgType
                if (bridge.cfg.bgDim !== undefined && Number(bridge.cfg.bgDim) > 0.05) root.bgDim = Number(bridge.cfg.bgDim)
                if (bridge.cfg.elemShowLyrics !== undefined) root.elemShowLyrics = bridge.cfg.elemShowLyrics
                if (bridge.cfg.elemShowCover !== undefined) root.elemShowCover = bridge.cfg.elemShowCover
                if (bridge.cfg.elemShowTitle !== undefined) root.elemShowTitle = bridge.cfg.elemShowTitle
                if (bridge.cfg.elemShowProgress !== undefined) root.elemShowProgress = bridge.cfg.elemShowProgress
                if (bridge.cfg.keybinds) { root.customKeys = Object.assign({}, bridge.cfg.keybinds); root.keymap = root.buildKeymap() }
            }
            function onToast(t) { toastText.text = t; toast.opacity = 1; toastTimer.restart() }
        }

        Keys.onPressed: (e) => { root.onKey(e); e.accepted = true }
        HoverHandler { onPointChanged: root.wake(); cursorShape: Qt.BlankCursor }

                // ───── user background video / image layer (QtMultimedia lazy-loaded via videoQml only when needed)
        Item {
            id: userBg
            anchors.fill: parent
            visible: (root.bgType === "video" || root.bgType === "image") && !root.bgVideoError
            z: -2

            Image {
                id: userImg
                anchors.fill: parent
                fillMode: Image.PreserveAspectCrop
                source: (root.bgType === "image" && root.userBgPath) ? (root.userBgPath.indexOf("file://") === 0 ? root.userBgPath : "file://" + root.userBgPath) : ""
                visible: root.bgType === "image" && source !== ""
                opacity: root.bgDim
            }

            Loader {
                id: bgVideoLoader
                anchors.fill: parent
                active: root.bgType === "video" && !root.bgVideoError && root.userBgPath !== "" && (bridge.cfg.videoQml || "") !== ""
                source: active ? bridge.cfg.videoQml : ""
                onLoaded: {
                    if (item) {
                        item.videoSource = (root.userBgPath.indexOf("file://") === 0 ? root.userBgPath : "file://" + root.userBgPath)
                        item.bgDim = Qt.binding(function() { return root.bgDim })
                        item.failed.connect(function() { root.bgVideoError = true })
                    }
                }
            }
        }

        // ───── fluid background: two slowly counter-rotating blurred covers + wandering colour clouds
        Item {
            id: bg
            anchors.fill: parent; clip: true
            visible: root.elemShowBgLayers && !root.cleanView
            Rectangle { anchors.fill: parent; color: Qt.darker(root.c1, 5) }
            Item {
                id: spin1
                anchors.centerIn: parent; width: Math.max(win.width, win.height) * 1.7; height: width
                opacity: 0.9
                NumberAnimation on rotation { from: 0; to: 360; duration: 150000; loops: Animation.Infinite; running: !root.lite }
                ArtLayer { id: artA; anchors.fill: parent }
            }
            Item {
                id: spin2
                anchors.centerIn: parent; width: Math.max(win.width, win.height) * 1.5; height: width
                opacity: 0.5; scale: 1.1
                NumberAnimation on rotation { from: 360; to: 0; duration: 210000; loops: Animation.Infinite; running: !root.lite }
                ArtLayer { id: artB; anchors.fill: parent }
            }
            Item {
                id: clouds
                anchors.fill: parent; opacity: 0.75
                SequentialAnimation on scale {
                    loops: Animation.Infinite; running: !root.lite
                    NumberAnimation { to: 1.08; duration: 14000; easing.type: Easing.InOutSine }
                    NumberAnimation { to: 1.0; duration: 14000; easing.type: Easing.InOutSine }
                }
                Blob { col: root.c1; fx: 0.18; fy: 0.30; size: 0.95; dur: 19000 }
                Blob { col: root.c2; fx: 0.82; fy: 0.22; size: 0.85; dur: 23000 }
                Blob { col: root.c3; fx: 0.50; fy: 0.90; size: 1.00; dur: 29000 }
                Blob { col: root.c1; fx: 0.92; fy: 0.85; size: 0.70; dur: 17000 }
            }
            // B key: Soft blurred album cover backdrop
            Image {
                id: backdropCover
                anchors.fill: parent
                fillMode: Image.PreserveAspectCrop
                mipmap: true
                smooth: true
                source: bridge.artInfo.mid ? bridge.artInfo.mid : bridge.artInfo.bg
                visible: root.backdrop
                opacity: root.backdrop ? 0.75 : 0
                Behavior on opacity { NumberAnimation { duration: 400 } }
            }
            Rectangle { anchors.fill: parent; color: Qt.rgba(0, 0, 0, 0.34) }
            Rectangle {
                anchors.fill: parent
                gradient: Gradient {
                    GradientStop { position: 0; color: Qt.rgba(0, 0, 0, 0.25) }
                    GradientStop { position: 0.5; color: Qt.rgba(0, 0, 0, 0) }
                    GradientStop { position: 1; color: Qt.rgba(0, 0, 0, 0.55) }
                }
            }
        }

        
        // Backdrop mode subtle bottom track caption
        Item {
            visible: root.backdrop && !root.cleanView && bridge.meta.title !== ""
            anchors.bottom: parent.bottom; anchors.bottomMargin: root.pad * 0.6
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.min(parent.width - root.pad * 2, bCaption.implicitWidth + 28)
            height: 32
            Rectangle { anchors.fill: parent; radius: 16; color: Qt.rgba(0, 0, 0, 0.45) }
            Text {
                id: bCaption; anchors.centerIn: parent
                text: bridge.meta.artist + "  ·  " + bridge.meta.title
                color: Qt.rgba(1, 1, 1, 0.85); font.pixelSize: 13; font.weight: Font.DemiBold
            }
        }
        // ───── cover, title, progress, controls (beside the lyrics, or above them in tall windows)
        GridLayout {
            id: side
            visible: !root.cleanView && !root.backdrop && (root.elemShowCover || root.elemShowTitle || root.elemShowProgress)
            columns: root.portrait ? 2 : 1
            columnSpacing: root.pad * 0.6
            rowSpacing: (root.portrait ? root.pad * 0.35 : win.height * 0.03) + root.coverTitleGap
            x: root.pad
            y: root.portrait ? root.pad : Math.max(root.pad, (win.height - height) / 2)
            width: root.sideW

            Item {
                id: card
                visible: root.elemShowCover && !root.cleanView
                Layout.preferredWidth: root.cardS; Layout.preferredHeight: root.cardS
                Layout.alignment: Qt.AlignTop
                scale: root.playing ? 1 : 0.94
                Behavior on scale { NumberAnimation { duration: 700; easing.type: Easing.OutCubic } }
                Rectangle { id: maskRect; anchors.fill: parent; radius: width * 0.05; color: "#15151b"; layer.enabled: true; visible: false }
                Rectangle { anchors.fill: parent; radius: width * 0.05; color: "#15151b" }
                Image {
                    id: art; anchors.fill: parent; source: bridge.artInfo.art; fillMode: Image.PreserveAspectCrop
                    sourceSize: Qt.size(720, 720); asynchronous: true; visible: root.lite
                }
                MultiEffect {
                    anchors.fill: parent; source: art; maskEnabled: true; maskSource: maskRect; visible: !root.lite
                    shadowEnabled: true; shadowColor: "black"; shadowOpacity: 0.55; shadowBlur: 1.0; shadowVerticalOffset: 22
                }
            }
            ColumnLayout {
                visible: root.elemShowTitle && !root.cleanView
                Layout.fillWidth: true
                Layout.alignment: root.portrait ? Qt.AlignVCenter : Qt.AlignTop
                spacing: 4
                Text { Layout.fillWidth: true; text: bridge.meta.title || ""; color: "white"; font.pixelSize: Math.round(root.u * 0.04)
                       font.weight: Font.ExtraBold; wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight }
                Text { Layout.fillWidth: true; text: bridge.meta.artist || ""; color: Qt.rgba(1, 1, 1, 0.78); font.pixelSize: Math.round(root.u * 0.027)
                       font.weight: Font.DemiBold; elide: Text.ElideRight }
                Text { Layout.fillWidth: true; text: bridge.meta.album || ""; color: Qt.rgba(1, 1, 1, 0.45); font.pixelSize: Math.round(root.u * 0.021); elide: Text.ElideRight }
            }
            // Polished Progress Bar with multiple styles & breathing room
            Item {
                id: progWrap
                visible: root.showProgress && root.elemShowProgress && !root.cleanView
                Layout.fillWidth: true
                Layout.preferredHeight: 34
                Layout.columnSpan: root.portrait ? 2 : 1
                readonly property real frac: root.len > 0 ? Math.max(0, Math.min(1, root.pos / root.len)) : 0

                // Style 0: Thin Glow Line
                Item {
                    visible: root.progressStyle === 0
                    width: parent.width; height: 8; y: 4
                    Rectangle {
                        anchors.centerIn: parent; width: parent.width; height: 3; radius: 1.5
                        color: Qt.rgba(1, 1, 1, 0.18)
                    }
                    Rectangle {
                        y: 2.5; height: 3; radius: 1.5
                        width: parent.width * progWrap.frac
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0.0; color: root.c1 }
                            GradientStop { position: 1.0; color: "white" }
                        }
                    }
                }

                // Style 1: Rounded Track with Glowing Dot
                Item {
                    visible: root.progressStyle === 1
                    width: parent.width; height: 12; y: 2
                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter; width: parent.width; height: 4; radius: 2
                        color: Qt.rgba(1, 1, 1, 0.22)
                    }
                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter; height: 4; radius: 2
                        width: parent.width * progWrap.frac; color: "white"
                    }
                    Rectangle {
                        x: Math.max(0, Math.min(parent.width - width, parent.width * progWrap.frac - width / 2))
                        anchors.verticalCenter: parent.verticalCenter
                        width: 10; height: 10; radius: 5; color: "white"
                        Rectangle {
                            anchors.centerIn: parent; width: 18; height: 18; radius: 9
                            color: Qt.rgba(1, 1, 1, 0.25); z: -1
                        }
                    }
                }

                // Style 2: Segmented Audio Waveform Track
                Row {
                    visible: root.progressStyle === 2
                    anchors.top: parent.top; anchors.topMargin: 2
                    width: parent.width; height: 12
                    spacing: Math.max(2, Math.floor((width - 40 * 3) / 39))
                    Repeater {
                        model: 40
                        delegate: Rectangle {
                            required property int index
                            readonly property real pFrac: (index + 0.5) / 40.0
                            readonly property bool active: pFrac <= progWrap.frac
                            width: 3
                            height: 4 + 8 * Math.abs(Math.sin((index + 1) * 0.7))
                            radius: 1.5
                            anchors.verticalCenter: parent.verticalCenter
                            color: active ? "white" : Qt.rgba(1, 1, 1, 0.20)
                            Behavior on color { ColorAnimation { duration: 120 } }
                        }
                    }
                }

                // Timestamps
                Text { y: 16; text: root.fmt(root.pos); color: Qt.rgba(1, 1, 1, 0.65); font.pixelSize: 12; font.weight: Font.Medium }
                Text { y: 16; anchors.right: parent.right; text: root.len > 0 ? root.fmt(root.len) : "--:--"; color: Qt.rgba(1, 1, 1, 0.65); font.pixelSize: 12; font.weight: Font.Medium }
            }
            Row {
                visible: root.controlsOn
                Layout.columnSpan: root.portrait ? 2 : 1
                Layout.alignment: root.portrait ? Qt.AlignHCenter : Qt.AlignLeft
                spacing: 8
                Icon { d: "M19,5 L9,12 L19,19 Z M7,5 H4 V19 H7 Z"; onClicked: bridge.prev() }
                Icon { d: root.playing ? "M6,4 H10 V20 H6 Z M14,4 H18 V20 H14 Z" : "M7,4 L20,12 L7,20 Z"; onClicked: bridge.playPause() }
                Icon { d: "M5,5 L15,12 L5,19 Z M17,5 H20 V19 H17 Z"; onClicked: bridge.next() }
            }
        }

        // ───── lyrics
        ListView {
            id: lv
            x: root.backdrop ? root.pad * 1.5 : (root.portrait ? root.pad : side.x + root.sideW + root.pad * 1.3)
            y: root.backdrop ? root.pad * 1.2 : (root.portrait ? side.y + side.height + root.pad * 0.5 : 0)
            width: root.backdrop ? (win.width - root.pad * 3.0) : (win.width - x - (root.portrait ? root.pad : root.pad * 1.3))
            height: root.backdrop ? (win.height - root.pad * 2.4) : (win.height - y)
            model: root.lines
            opacity: root.wordMode && root.kind === "synced" ? 0 : 1
            visible: opacity > 0.01 && root.elemShowLyrics && !root.cleanView
            Behavior on opacity { NumberAnimation { duration: 320 } }
            clip: true; cacheBuffer: 480
            interactive: root.kind !== "synced"
            currentIndex: Math.max(0, root.activeIdx)
            highlightRangeMode: root.kind === "synced" ? ListView.StrictlyEnforceRange : ListView.NoHighlightRange
            preferredHighlightBegin: height * 0.30
            preferredHighlightEnd: height * 0.30 + 1
            highlightMoveDuration: 650
            highlightMoveVelocity: -1
            delegate: Item {
                id: row
                required property int index
                required property var modelData
                readonly property bool synced: root.kind === "synced"
                readonly property int dist: index - root.activeIdx
                readonly property bool on: synced && dist === 0
                readonly property bool isGap: modelData.gap === true
                width: ListView.view ? ListView.view.width : 0
                height: (isGap ? root.fs * 1.2 : (modelData.text !== undefined ? txt.height : flow.height)) + root.fs * 0.55
                opacity: !synced ? 0.88 : on ? 1 : Math.max(0.1, 0.5 - 0.09 * Math.abs(dist))
                scale: !synced || on ? 1 : 0.93
                transformOrigin: Item.Left
                Behavior on opacity { NumberAnimation { duration: 420 } }
                Behavior on scale { NumberAnimation { duration: 420; easing.type: Easing.OutCubic } }

                Text {
                    id: txt; visible: modelData.text !== undefined; width: parent.width * 0.94; y: root.fs * 0.27
                    text: modelData.text === undefined ? "" : (modelData.text || " "); color: "white"; wrapMode: Text.WordWrap
                    font.pixelSize: Math.round(root.fs * 0.8); font.weight: Font.Bold
                }
                Flow {
                    id: flow; visible: !row.isGap && modelData.words !== undefined; width: parent.width * 0.94; y: root.fs * 0.27
                    Repeater {
                        model: row.modelData.words ? row.modelData.words : []
                        delegate: Item {
                            id: wd
                            required property var modelData
                            readonly property real tw: tm.advanceWidth
                            readonly property real p: row.on
                                ? Math.max(0, Math.min(1, (root.pos + root.offset - modelData.t) / Math.max(0.05, modelData.e - modelData.t)))
                                : (row.dist < 0 ? 1 : 0)
                            width: tw + (modelData.s ? root.fs * 0.28 : 0)
                            height: root.fs * 1.28
                            TextMetrics { id: tm; font: root.lyricFont; text: wd.modelData.w }
                            Item {
                                width: wd.tw; height: parent.height
                                y: wd.p > 0 ? -root.fs * 0.05 : 0
                                Behavior on y { NumberAnimation { duration: 280; easing.type: Easing.OutCubic } }
                                Text { text: wd.modelData.w; font: root.lyricFont; color: Qt.rgba(1, 1, 1, 0.30) }
                                Text { visible: wd.p >= 1; text: wd.modelData.w; font: root.lyricFont; color: "white" }
                                Loader { active: wd.p > 0 && wd.p < 1; sourceComponent: wipeC }
                                Component {
                                    id: wipeC
                                    SoftWipe { word: wd.modelData.w; fnt: root.lyricFont; p: wd.p; tw: wd.tw; h: wd.height; edge: root.fs * 0.5; glow: 0.7 }
                                }
                            }
                        }
                    }
                }
                Row {   // instrumental gap: three dots that fill up
                    visible: row.isGap; spacing: root.fs * 0.35; y: root.fs * 0.3
                    Repeater {
                        model: 3
                        delegate: Rectangle {
                            required property int index
                            readonly property real q: row.on
                                ? Math.max(0, Math.min(1, ((root.pos + root.offset - row.modelData.t) / Math.max(0.1, row.modelData.e - row.modelData.t)) * 3 - index))
                                : (row.dist < 0 ? 1 : 0)
                            width: root.fs * 0.42; height: width; radius: width / 2; color: "white"
                            opacity: 0.25 + 0.75 * q
                            scale: (0.8 + 0.3 * q) * (row.on && q > 0 ? 1 + 0.1 * Math.sin(root.pos * 3 + index) : 1)
                        }
                    }
                }
                            }
        }

        Text {
            visible: bridge.kind === "none" || bridge.kind === "loading"
            x: lv.x; width: lv.width; y: lv.y + lv.height * 0.3
            text: bridge.kind === "loading" ? "…" : "No lyrics found for this track"
            color: Qt.rgba(1, 1, 1, 0.5); font.pixelSize: Math.round(root.u * 0.04); font.weight: Font.Bold; wrapMode: Text.WordWrap
        }


        // ───── word mode: Stack (0) / Edit (1) / Rain (2) (T cycles the style)
        Item {
            id: wv
            x: lv.x; y: lv.y; width: lv.width; height: lv.height
            opacity: root.wordMode && root.kind === "synced" ? 1 : 0
            visible: opacity > 0.01 && root.elemShowLyrics && !root.cleanView
            Behavior on opacity { NumberAnimation { duration: 320 } }
            readonly property int st: root.wordStyle
            readonly property real tnow: root.pos + root.offset
            readonly property int fi: root.flatIdx(tnow)
            readonly property var curItem: fi >= 0 && fi < root.flat.length ? root.flat[fi] : null
            readonly property real p: curItem ? Math.max(0, Math.min(1, (tnow - curItem.t) / Math.max(0.05, curItem.e - curItem.t))) : 0
            readonly property bool isGap: {
                var l = root.lines[root.activeIdx]
                return l !== undefined && l.gap === true
            }

            property int prevFi: -1
            property real laneSeq: 0.3
            property int rainIdx: 0
            property var spawnedRain: ({})

            property string lastMainWord: ""

            onCurItemChanged: {
                if (curItem && fi !== prevFi) {
                    prevFi = fi
                    lastMainWord = curItem.w
                    if (st === 1) editWord.trigger()
                    else if (st === 0) root.punch()
                }
            }

            onIsGapChanged: {
                if (isGap) {
                    lastMainWord = ""
                }
            }

            onStChanged: {
                spawnedRain = ({})
                if (st === 1 && curItem) {
                    editWord.trigger()
                }
            }

            // Warning badge when lyrics are not word-by-word
            Row {
                visible: !bridge.wordLevel && wv.visible
                anchors.top: parent.top; anchors.topMargin: root.pad * 0.4
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 6
                Rectangle {
                    width: warnTxt.implicitWidth + 24; height: warnTxt.implicitHeight + 10
                    radius: height / 2; color: Qt.rgba(0.9, 0.6, 0.1, 0.22)
                    border.color: Qt.rgba(0.9, 0.6, 0.1, 0.65); border.width: 1
                    Text {
                        id: warnTxt; anchors.centerIn: parent
                        text: "⚠ Estimated word timing (line-level LRC)"
                        color: "#ffb142"; font.pixelSize: Math.round(root.fs * 0.46); font.weight: Font.DemiBold
                    }
                }
            }

            // 1. STACK STYLE (0): Vertical ListView of single words, scrolling with distance fade
            ListView {
                id: lvStack
                visible: wv.st === 0
                opacity: wv.isGap ? 0.0 : 1.0
                Behavior on opacity { NumberAnimation { duration: 250 } }
                anchors.fill: parent
                model: root.flat
                clip: true
                currentIndex: Math.max(0, wv.fi)
                highlightRangeMode: ListView.StrictlyEnforceRange
                preferredHighlightBegin: height * 0.42
                preferredHighlightEnd: height * 0.42 + 1
                highlightMoveDuration: 280
                highlightMoveVelocity: -1
                spacing: root.fs * 0.35

                delegate: Item {
                    id: stkRow
                    required property int index
                    required property var modelData
                    readonly property int dist: index - lvStack.currentIndex
                    readonly property bool on: dist === 0
                    width: lvStack.width
                    height: Math.round(root.fs * 1.9)
                    opacity: on ? 1.0 : Math.max(0.10, 0.45 - 0.11 * Math.abs(dist))
                    scale: on ? 1.18 : Math.max(0.82, 1.0 - 0.06 * Math.abs(dist))
                    transformOrigin: Item.Center

                    Behavior on opacity { NumberAnimation { duration: 240 } }
                    Behavior on scale { NumberAnimation { duration: 240; easing.type: Easing.OutCubic } }

                    GlowText {
                        id: gtStack
                        anchors.centerIn: parent
                        text: stkRow.modelData.w
                        col: stkRow.on ? "white" : Qt.rgba(1, 1, 1, 0.70)
                        fnt: Qt.font({ family: root.lyricFont.family,
                                       pixelSize: Math.round(root.fs * 1.45),
                                       weight: stkRow.on ? Font.Black : Font.Bold })
                        glow: stkRow.on ? 1.0 : 0
                    }
                }
            }

            // 2. EDIT STYLE (1): Kinetic typography 'edit video' feel, bold single word, pop-in, tilt, punch, color accents, stretch
            Item {
                id: editWord
                visible: wv.st === 1 && (wv.curItem !== null || wv.lastMainWord !== "") && !wv.isGap
                anchors.fill: parent
                property real popScale: 1.0
                property real tilt: 0.0
                property real xShift: 0.0
                property real yShift: 0.0
                property color wordCol: "white"
                function trigger() {
                    var w = wv.curItem ? wv.curItem.w : (wv.lastMainWord !== "" ? wv.lastMainWord : "")
                    if (!w) return
                    root.punch()
                    var hash = 0
                    for (var i = 0; i < w.length; i++) hash = (hash * 31 + w.charCodeAt(i)) & 0x7fffffff
                    tilt = ((hash % 11) - 5) * 1.9
                    xShift = ((hash % 7) - 3) * 7
                    yShift = (((hash >> 3) % 7) - 3) * 6
                    var mod = hash % 6
                    wordCol = (mod === 0) ? root.c1 : (mod === 1) ? root.c2 : (mod === 2) ? root.c3 : "white"
                    popScale = 1.32
                    popAnim.restart()
                }

                NumberAnimation {
                    id: popAnim
                    target: editWord; property: "popScale"; from: 1.32; to: 1.0
                    duration: 200; easing.type: Easing.OutBack
                }

                Item {
                    id: editBox
                    width: gtEdit.width; height: gtEdit.height
                    anchors.centerIn: parent
                    anchors.horizontalCenterOffset: editWord.xShift
                    anchors.verticalCenterOffset: editWord.yShift
                    rotation: editWord.tilt
                    scale: editWord.popScale * Math.min(1.0, (parent.width * 0.88) / Math.max(1, gtEdit.width))

                    readonly property real dur: wv.curItem ? Math.max(0.1, wv.curItem.e - wv.curItem.t) : 0.4
                    readonly property bool isSustained: dur > 0.75
                    readonly property real stretch: isSustained ? (1.0 + 0.28 * Math.sin(wv.p * Math.PI * 0.5)) : 1.0

                    transform: Scale { xScale: editBox.stretch; origin.x: editBox.width / 2; origin.y: editBox.height / 2 }

                    GlowText {
                        id: gtEdit
                        anchors.centerIn: parent
                        text: wv.lastMainWord !== "" ? wv.lastMainWord : (wv.curItem ? wv.curItem.w : "")
                        col: editWord.wordCol
                        fnt: Qt.font({ family: bridge.cfg.font ? bridge.cfg.font : Qt.application.font.family,
                                       pixelSize: Math.max(28, Math.round(Math.min(win.width * 0.16, win.height * 0.22))),
                                       weight: Font.Black })
                        glow: 1.0
                    }
                }
            }

            // 3. RAIN STYLE (2): Deterministic audio-clock fall with water ripples and smooth vapor fade-away
            Item {
                id: rainView
                visible: wv.st === 2
                anchors.fill: parent

                readonly property real groundY: height * 0.62
                readonly property real fallDur: 1.0 // exactly 1.0s fall duration
                readonly property real fadeDur: 0.85 // smooth vapor fade-away after singing ends

                // Window of words around current playback time (time-bounded lookahead so CJK/dense lyrics never clip)
                readonly property int curFi: Math.max(0, root.flatIdx(wv.tnow))
                Repeater {
                    model: 24
                    delegate: Item {
                        id: rDrop
                        required property int index

                        // Map fixed pool slot to the unique word index in flat lyrics array
                        readonly property int wordIdx: {
                            if (!root.flat || !root.flat.length) return -1
                            var cf = rainView.curFi
                            var slot = index
                            var base = Math.floor((cf - 6) / 24) * 24 + slot
                            if (base < cf - 6) base += 24
                            return (base >= 0 && base < root.flat.length) ? base : -1
                        }

                        readonly property var wData: wordIdx >= 0 ? root.flat[wordIdx] : null
                        readonly property real tRemain: wData ? (wData.t - wv.tnow) : 999
                        readonly property bool isFalling: wData ? (tRemain > 0 && tRemain <= rainView.fallDur) : false
                        readonly property bool isPastEnd: wData ? (wv.tnow > wData.e) : false
                        readonly property real tPastEnd: isPastEnd ? (wv.tnow - wData.e) : 0.0
                        readonly property real fadeProgress: Math.min(1.0, Math.max(0.0, tPastEnd / rainView.fadeDur))
                        readonly property bool isSung: wData ? (tRemain <= 0 && wv.tnow <= (wData.e + rainView.fadeDur)) : false

                        visible: (isFalling || isSung) && (wData !== null)

                        // Fall progress from 0 (top of screen) to 1.0 (exact ground level)
                        readonly property real fallProgress: isFalling ? Math.min(1.0, Math.max(0.0, 1.0 - (tRemain / rainView.fallDur))) : 1.0

                        // Landing ripple progress (from 0 to 1 over 0.65s after landing)
                        readonly property real tSinceLand: wData ? (wv.tnow - wData.t) : -1.0
                        readonly property bool showRipple: wData && (tSinceLand >= 0.0) && (tSinceLand <= 0.65)
                        readonly property real ripP: showRipple ? Math.min(1.0, Math.max(0.0, tSinceLand / 0.65)) : 0.0

                        // Y position: falls to groundY, then gently drifts upward like vapor while fading
                        y: isFalling
                           ? (fallProgress * fallProgress * (rainView.groundY + height)) - height
                           : (rainView.groundY - fadeProgress * 16)

                        // Stable horizontal lane derived from word metadata
                        readonly property real lane: {
                            if (!wData || !wData.w) return 0.5
                            var hash = 0
                            var s = wData.w
                            for (var k = 0; k < s.length; k++) hash = (hash * 31 + s.charCodeAt(k)) & 0x7fffffff
                            return 0.12 + 0.76 * (((wData.line * 7 + wData.k * 13 + hash) % 100) / 100.0)
                        }

                        x: Math.max(16, Math.min(parent.width - width - 16, parent.width * lane - width / 2))
                        width: rText.implicitWidth; height: rText.implicitHeight

                        scale: isFalling
                               ? (0.75 + 0.25 * fallProgress)
                               : isSung
                                 ? (isPastEnd
                                    ? (1.0 + 0.08 * fadeProgress)
                                    : (1.0 + 0.22 * Math.sin(Math.min(1.0, (wv.tnow - (wData ? wData.t : 0)) / 0.14) * Math.PI)))
                                 : 0.5

                        opacity: isFalling
                                 ? (fallProgress < 0.15 ? fallProgress / 0.15 : 1.0)
                                 : (isPastEnd
                                    ? Math.max(0.0, Math.pow(1.0 - fadeProgress, 1.8))
                                    : 1.0)

                        // Water ripple 1: Primary expanding water ring
                        Rectangle {
                            visible: rDrop.showRipple
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.verticalCenter: parent.bottom
                            width: Math.max(36, rText.implicitWidth * (0.6 + 2.2 * rDrop.ripP))
                            height: width * 0.28
                            radius: width / 2
                            color: "transparent"
                            border.width: Math.max(1.0, 2.0 * (1.0 - rDrop.ripP))
                            border.color: Qt.rgba(root.c1.r, root.c1.g, root.c1.b, 0.85 * Math.pow(1.0 - rDrop.ripP, 1.3))
                            z: -2
                        }

                        // Water ripple 2: Secondary inner echo ring
                        Rectangle {
                            readonly property real ripP2: Math.max(0.0, (rDrop.ripP - 0.16) / 0.84)
                            visible: rDrop.showRipple && rDrop.ripP >= 0.16
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.verticalCenter: parent.bottom
                            width: Math.max(20, rText.implicitWidth * (0.35 + 1.5 * ripP2))
                            height: width * 0.28
                            radius: width / 2
                            color: "transparent"
                            border.width: 1.0
                            border.color: Qt.rgba(root.c2.r, root.c2.g, root.c2.b, 0.6 * Math.pow(1.0 - ripP2, 1.3))
                            z: -2
                        }

                        // Water splash droplet glow at point of impact
                        Rectangle {
                            visible: rDrop.showRipple && rDrop.ripP < 0.22
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.verticalCenter: parent.bottom
                            width: Math.max(12, rText.implicitWidth * 0.4 * (1.0 - rDrop.ripP / 0.22))
                            height: width * 0.35
                            radius: width / 2
                            color: Qt.rgba(1, 1, 1, 0.45 * (1.0 - rDrop.ripP / 0.22))
                            z: -1
                        }

                        GlowText {
                            id: rText
                            anchors.centerIn: parent
                            text: rDrop.wData ? rDrop.wData.w : ""
                            col: rDrop.isSung ? "white" : Qt.rgba(1, 1, 1, 0.85)
                            fnt: Qt.font({ family: root.lyricFont.family,
                                           pixelSize: Math.max(22, Math.round(root.fs * (rDrop.isSung ? 1.5 : 1.3))),
                                           weight: Font.Black })
                            glow: rDrop.isSung ? 1.0 : (rDrop.isFalling ? (0.3 + 0.5 * rDrop.fallProgress) : 0.4)
                        }
                    }
                }
            }

            // Instrumental gap indicator in word mode
            Row {
                id: gapIndicator
                visible: wv.isGap
                opacity: visible ? 1.0 : 0.0
                Behavior on opacity { NumberAnimation { duration: 250 } }
                anchors.centerIn: parent
                spacing: root.fs * 0.6
                Repeater {
                    model: 3
                    delegate: Rectangle {
                        required property int index
                        readonly property var curL: root.lines[root.activeIdx]
                        readonly property real q: curL && curL.gap
                            ? Math.max(0, Math.min(1, ((wv.tnow - curL.t) / Math.max(0.1, curL.e - curL.t)) * 3 - index)) : 0
                        width: root.fs * 0.7; height: width; radius: width / 2; color: "white"
                        opacity: 0.25 + 0.75 * q
                        scale: (0.8 + 0.3 * q) * (q > 0 ? 1 + 0.08 * Math.sin(root.pos * 4 + index) : 1)
                    }
                }
            }
        }

        // ───── nothing playing
        Rectangle {
            anchors.fill: parent; color: "#050507"; opacity: bridge.meta.active ? 0 : 1; visible: opacity > 0.01
            Behavior on opacity { NumberAnimation { duration: 500 } }
            Text { anchors.centerIn: parent; horizontalAlignment: Text.AlignHCenter; color: Qt.rgba(1, 1, 1, 0.6); font.pixelSize: Math.round(root.u * 0.04)
                   font.weight: Font.Bold
                   text: bridge.libInfo.ready ? "" : bridge.libInfo.scanning ? "Scanning your music…" : "No songs found in\n" + bridge.libInfo.dir }
        }


        // ───── overlays - only ever shown by a key
        Rectangle {
            id: dim
            anchors.fill: parent; color: Qt.rgba(0, 0, 0, 0.55)
            opacity: root.overlay !== "" ? 1 : 0; visible: opacity > 0.01
            Behavior on opacity { NumberAnimation { duration: 200 } }
        }
        Item {
            id: panel
            anchors.centerIn: parent
            width: Math.min(win.width - 2 * root.pad, root.overlay === "help" ? 1000 : 920)
            height: Math.min(win.height - 2 * root.pad, win.height * (root.overlay === "help" ? 0.84 : 0.82))
            opacity: dim.opacity; visible: dim.visible; scale: 0.96 + 0.04 * dim.opacity
            Rectangle { anchors.fill: parent; radius: 24; color: Qt.rgba(0.045, 0.045, 0.06, 0.97); border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.10) }
            ColumnLayout {
                anchors.fill: parent; anchors.margins: Math.max(18, root.pad * 0.6); spacing: root.pad * 0.3
                RowLayout {
                    Layout.fillWidth: true; spacing: root.pad * 0.5
                    Text { text: ({ help: "Keybinds", queue: "Up next", "get-music": "Get Music", search: "Get Music", download: "Get Music", pick: "Library", settings: "Settings" })[root.overlay] || ""
                           color: "white"; font.pixelSize: Math.round(root.u * 0.044); font.weight: Font.ExtraBold }
                    Text { visible: (root.overlay === "pick" && root.drillSpec !== "") || (root.overlay === "get-music" && root.albumDrillBrowseId !== ""); Layout.fillWidth: true
                           text: "‹  " + (root.overlay === "get-music" ? root.albumDrillTitle : root.drillLabel); color: Qt.rgba(1, 1, 1, 0.6); elide: Text.ElideRight
                           font.pixelSize: Math.round(root.u * 0.03); font.weight: Font.DemiBold }
                    Item { Layout.fillWidth: true; visible: !((root.overlay === "pick" && root.drillSpec !== "") || (root.overlay === "get-music" && root.albumDrillBrowseId !== "")) }
                    Repeater {
                        model: root.overlay === "pick" ? ["albums", "artists", "songs"]
                             : root.overlay === "get-music" ? ["songs", "albums"]
                             : root.overlay === "settings" ? ["Display", "Audio & Library", "Background & Media", "Keybinds"] : []
                        delegate: Text {
                            required property int index
                            required property string modelData
                            readonly property bool on: root.overlay === "pick" ? root.pickKind === modelData
                                                      : root.overlay === "get-music" ? root.getMusicTab === modelData
                                                      : root.overlay === "settings" ? root.setTab === index : true
                            text: modelData.charAt(0).toUpperCase() + modelData.slice(1)
                            color: on ? "white" : Qt.rgba(1, 1, 1, 0.38); font.pixelSize: Math.round(root.u * 0.028); font.weight: Font.Bold
                            Rectangle { y: parent.height + 3; height: 2; radius: 1; color: root.c1; width: parent.on ? parent.width : 0; Behavior on width { NumberAnimation { duration: 180 } } }
                        }
                    }
                }
                Item {   // filter line
                    Layout.fillWidth: true; Layout.preferredHeight: Math.round(root.u * 0.05)
                    visible: root.overlay === "pick" || root.overlay === "get-music" || root.overlay === "search" || root.overlay === "download"
                    Rectangle { anchors.fill: parent; radius: height / 2; color: Qt.rgba(1, 1, 1, 0.07) }
                    Text { x: 18; anchors.verticalCenter: parent.verticalCenter; font.pixelSize: Math.round(root.u * 0.026); font.weight: Font.DemiBold
                           color: root.filter === "" ? Qt.rgba(1, 1, 1, 0.35) : "white"
                           text: root.filter !== "" ? root.filter : root.overlay === "get-music" ? (root.getMusicTab === "songs" ? "Search songs (Enter stream, Shift+Enter queue)" : "Search albums (Enter view tracks album)") : "type to filter" }
                    Rectangle { visible: root.filter !== ""; x: 20 + fm.advanceWidth; anchors.verticalCenter: parent.verticalCenter; width: 2; height: parent.height * 0.5; color: root.c1
                                SequentialAnimation on opacity { loops: Animation.Infinite; NumberAnimation { to: 0.1; duration: 500 } NumberAnimation { to: 1; duration: 500 } } }
                    TextMetrics { id: fm; text: root.filter; font.pixelSize: Math.round(root.u * 0.026); font.weight: Font.DemiBold }
                }
                Item {
                    Layout.fillWidth: true; Layout.fillHeight: true
                    GridView {   // album / artist covers
                        id: pgrid
                        anchors.fill: parent; visible: root.isGrid; clip: true; model: root.isGrid ? root.shown : []
                        property int cols: Math.max(2, Math.floor(width / (root.u * 0.27)))
                        onColsChanged: root.gridCols = cols
                        cellWidth: width / cols; cellHeight: cellWidth * 1.34
                        currentIndex: root.sel
                        onCurrentIndexChanged: positionViewAtIndex(currentIndex, GridView.Contain)
                        delegate: Item {
                            required property int index
                            required property var modelData
                            width: pgrid.cellWidth; height: pgrid.cellHeight
                            Rectangle { anchors.fill: parent; anchors.margins: 4; radius: 14; visible: index === root.sel; color: Qt.rgba(root.c1.r, root.c1.g, root.c1.b, 0.38) }
                            Column {
                                anchors.fill: parent; anchors.margins: 10; spacing: 6
                                Item {
                                    width: parent.width; height: parent.width
                                    Rectangle { anchors.fill: parent; radius: 10; color: "#1b1b24"; visible: th.status !== Image.Ready
                                                Text { anchors.centerIn: parent; text: "♪"; color: Qt.rgba(1, 1, 1, 0.25); font.pixelSize: parent.width * 0.4 } }
                                    Image { id: th; anchors.fill: parent; source: modelData.thumb || ""; fillMode: Image.PreserveAspectCrop; asynchronous: true; sourceSize: Qt.size(300, 300) }
                                }
                                Text { width: parent.width; text: modelData.name; color: "white"; elide: Text.ElideRight; font.pixelSize: Math.round(root.u * 0.024); font.weight: Font.DemiBold }
                                Text { width: parent.width; text: modelData.sub || ""; color: Qt.rgba(1, 1, 1, 0.5); elide: Text.ElideRight; font.pixelSize: Math.round(root.u * 0.019) }
                            }
                        }
                    }
                    ListView {   // songs, queue, search, download results
                        id: plist
                        anchors.fill: parent; visible: root.overlay !== "help" && root.overlay !== "settings" && !root.isGrid; clip: true; model: root.isGrid ? [] : root.shown
                        currentIndex: root.sel
                        onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)
                        delegate: Item {
                            required property int index
                            required property var modelData
                            width: ListView.view.width; height: Math.round(root.u * 0.08)
                            Rectangle { anchors.fill: parent; anchors.margins: 2; radius: 14; visible: index === root.sel; color: Qt.rgba(root.c1.r, root.c1.g, root.c1.b, 0.38) }
                            Column {
                                anchors.left: parent.left; anchors.leftMargin: 16 + (modelData.depth || 0) * 28; anchors.right: cnt.left; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter
                                Text { width: parent.width; elide: Text.ElideRight; color: "white"; font.pixelSize: Math.round(root.u * 0.029); font.weight: Font.DemiBold
                                       text: (modelData.group ? (modelData.open ? "▾ " : "▸ ") : "") + modelData.name }
                                Text { width: parent.width; text: modelData.sub || ""; color: Qt.rgba(1, 1, 1, 0.5); elide: Text.ElideRight; font.pixelSize: Math.round(root.u * 0.02) }
                            }
                            Text { id: cnt; anchors.right: parent.right; anchors.rightMargin: 18; anchors.verticalCenter: parent.verticalCenter
                                   color: Qt.rgba(1, 1, 1, 0.45); font.pixelSize: Math.round(root.u * 0.022)
                                   text: root.overlay === "queue" ? (modelData.group ? modelData.n + " songs" : (modelData.depth ? "" : (modelData.path ? "#" + (modelData.path[0] + 1) : ""))) : (modelData.dur || "") }
                        }
                    }
                    
                    // ───── Settings list view (scrollable ListView, never overflows!)
                    Item {
                        anchors.fill: parent; visible: root.overlay === "settings"
                        ListView {
                            id: setList
                            anchors.fill: parent
                            clip: true
                            spacing: 8
                            currentIndex: root.setSel
                            onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)
                            model: {
                                if (root.setTab === 0) return [
                                    ["Word Mode Style", root.styleNames[root.wordStyle], "T to cycle"],
                                    ["Progress Bar Style", ["Glow Line", "Dot Pill", "Waveform"][root.progressStyle], "Left / Right to change"],
                                    ["Cover Spacing", root.coverTitleGap + "px", "Left / Right to adjust"],
                                    ["Show Progress Bar", root.elemShowProgress ? "Yes" : "No", "Left / Right to toggle"]
                                ]
                                if (root.setTab === 1) return [
                                    ["Volume", Math.round(root.vol * 100) + "%", "Up / Down / Left / Right"],
                                    ["Lyric Timing Offset", (root.offset >= 0 ? "+" : "") + root.offset.toFixed(1) + "s", "[ ] keys"],
                                    ["Word Timing Spread", "x" + root.spreadVal.toFixed(2), ", . keys"],
                                    ["Reshuffle Library", "Press Enter to reshuffle", "M key"],
                                    ["Rescan Music Folder", "Press Enter to rescan", "Ctrl+R"]
                                ]
                                if (root.setTab === 2) return [
                                    ["Background Type", root.bgType, "Left / Right to cycle"],
                                    ["Background Dim", Math.round(root.bgDim * 100) + "%", "Left / Right to adjust"],
                                    ["Show Lyrics", root.elemShowLyrics ? "Yes" : "No", "Left / Right to toggle"],
                                    ["Show Cover Art", root.elemShowCover ? "Yes" : "No", "Left / Right to toggle"],
                                    ["Show Track Title", root.elemShowTitle ? "Yes" : "No", "Left / Right to toggle"],
                                    ["Clean View (Video Mode)", root.cleanView ? "Enabled" : "Disabled", "Press Enter or V"]
                                ]
                                var rows = []
                                for (var i = 0; i < root.actionSpecs.length; i++) {
                                    var s = root.actionSpecs[i]
                                    rows.push([s.label, root.keyFor(s.id), "Enter remap · Del reset"])
                                }
                                return rows
                            }
                            delegate: Item {
                                required property int index
                                required property var modelData
                                width: ListView.view.width; height: Math.round(root.u * 0.065)
                                Rectangle {
                                    anchors.fill: parent; radius: 10
                                    color: index === root.setSel ? Qt.rgba(root.c1.r, root.c1.g, root.c1.b, 0.40) : Qt.rgba(1, 1, 1, 0.04)
                                }
                                RowLayout {
                                    anchors.fill: parent; anchors.leftMargin: 16; anchors.rightMargin: 16
                                    Text { text: modelData[0]; color: "white"; font.pixelSize: Math.round(root.u * 0.026); font.weight: Font.DemiBold }
                                    Item { Layout.fillWidth: true }
                                    Text {
                                        text: (root.keyListening && root.setTab === 3 && index === root.setSel) ? "‹ Press any key… ›" : "‹ " + modelData[1] + " ›"
                                        color: (root.keyListening && root.setTab === 3 && index === root.setSel) ? "#ffb142" : "white"
                                        font.pixelSize: Math.round(root.u * 0.026); font.weight: Font.Bold
                                    }
                                    Text { text: modelData[2] ? "(" + modelData[2] + ")" : ""; color: Qt.rgba(1, 1, 1, 0.45); font.pixelSize: Math.round(root.u * 0.02) }
                                }
                            }
                        }
                    }
                    GridLayout {   // keybind sheet
                        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; visible: root.overlay === "help"
                        columns: win.width < 900 ? 1 : 2; columnSpacing: root.pad; rowSpacing: 0
                        flow: GridLayout.TopToBottom; rows: win.width < 900 ? root.keymap.length : Math.ceil(root.keymap.length / 2)
                        Repeater {
                            model: root.keymap
                            delegate: RowLayout {
                                required property var modelData
                                Layout.fillWidth: true; Layout.preferredHeight: Math.round(root.u * 0.051); spacing: 14
                                Rectangle { Layout.preferredWidth: Math.round(root.u * 0.15); Layout.preferredHeight: Math.round(root.u * 0.04); radius: 9
                                            color: Qt.rgba(1, 1, 1, 0.10); border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.14)
                                            Text { anchors.centerIn: parent; text: modelData[0]; color: "white"; font.pixelSize: Math.round(root.u * 0.02); font.weight: Font.Bold } }
                                Text { Layout.fillWidth: true; text: modelData[1]; color: Qt.rgba(1, 1, 1, 0.78); elide: Text.ElideRight
                                       font.pixelSize: Math.round(root.u * 0.022); font.weight: Font.DemiBold }
                            }
                        }
                    }
                    Text {   // empty states
                        anchors.centerIn: parent; width: parent.width * 0.8; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
                        visible: root.shown.length === 0 && root.overlay !== "help" && root.overlay !== "settings"; color: Qt.rgba(1, 1, 1, 0.45); font.pixelSize: Math.round(root.u * 0.028)
                        text: root.overlay === "queue"
                              ? (bridge.isStreaming ? "Streaming from YouTube Music.\nPress M to exit streaming and play your music library." : "The queue is empty.\nAdd albums or songs with Shift+Enter - then the shuffle carries on.")
                              : (root.overlay === "search" || root.overlay === "download" || root.overlay === "get-music")
                                ? (root.searchNote !== "" ? root.searchNote : (root.getMusicTab === "songs" ? "Type a song or artist to search YouTube Music" : "Type an album name to search YouTube Music"))
                              : bridge.libInfo.scanning && !bridge.libInfo.ready ? "Scanning your music…" : root.filter !== "" ? "Nothing matches" : "No songs found"
                    }
                }
                Column {   // download progress
                    visible: (root.overlay === "get-music" || root.overlay === "download") && root.dlJobs.length > 0; Layout.fillWidth: true; spacing: 2
                    Repeater {
                        model: (root.overlay === "get-music" || root.overlay === "download") ? root.dlJobs.slice(-3) : []
                        delegate: Text {
                            required property var modelData
                            width: parent.width; elide: Text.ElideRight; font.pixelSize: Math.round(root.u * 0.022); font.weight: Font.DemiBold
                            color: modelData.state === "failed" ? "#ff8a8a" : modelData.state === "done" ? "#9be39b" : Qt.rgba(1, 1, 1, 0.7)
                            text: (modelData.state === "done" ? "✔ " : modelData.state === "failed" ? "✘ " : "↓ ") + modelData.title + "  ·  " + (modelData.note || modelData.state)
                        }
                    }
                }
                Text {
                    Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap; color: Qt.rgba(1, 1, 1, 0.38)
                    font.pixelSize: Math.round(root.u * 0.02); font.weight: Font.DemiBold
                    text: root.overlay === "help" ? "In lists: type to filter · arrows move · Enter play · Shift+Enter queue · Tab next list · Ctrl+→ open (artist → albums, album → songs) · Ctrl+← back"
                        : root.overlay === "settings" ? "↑ ↓ select · ← → change · Tab switch tab · Enter activate / remap · Del reset key · Esc close"
                        : root.overlay === "queue" ? "↑ ↓ select · Shift+↑↓ move · → expand album · ← collapse · Enter play now · Del remove · Shift+Del clear · Esc"
                        : root.overlay === "get-music" ? (root.albumDrillBrowseId !== "" ? "↑ ↓ select track · Enter stream · Shift+Enter queue · Backspace back to albums · Esc close" : (root.getMusicTab === "songs" ? "type to search · ↑ ↓ · Enter stream · Shift+Enter queue · Ctrl+D download · Tab switch to albums · Esc close" : "type to search albums · ↑ ↓ · Enter view tracks · Tab switch to songs · Esc close"))
                        : "arrows move · Enter play · Shift+Enter queue · Ctrl+→ open · Ctrl+← back · Tab albums/artists/songs · Esc"
                }
            }
        }

        // ───── toast + hint
        Rectangle {
            id: toast
            visible: root.elemShowToasts && !root.cleanView; opacity: 0; anchors.horizontalCenter: parent.horizontalCenter; y: parent.height - height - win.height * 0.05
            width: Math.min(toastText.implicitWidth + 36, win.width - 20); height: toastText.height + 18; radius: height / 2; color: Qt.rgba(0, 0, 0, 0.55)
            Behavior on opacity { NumberAnimation { duration: 250 } }
            Text { id: toastText; anchors.centerIn: parent; width: parent.width - 28; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
                   color: "white"; font.pixelSize: 16; font.weight: Font.DemiBold }
            Timer { id: toastTimer; interval: 1600; onTriggered: toast.opacity = 0 }
        }
        Component.onCompleted: { forceActiveFocus(); toastText.text = "F1 · all keybinds"; toast.opacity = 1; toastTimer.interval = 3500; toastTimer.restart() }
    }
}
"""


def _write_cached_qml():
    """Write QML to disk cache only when changed so Qt reuses qmlcache bytecode across launches."""
    CACHE.mkdir(parents=True, exist_ok=True)
    main_qml = CACHE / "qt-music-ui.qml"
    video_qml = CACHE / "qt-music-video.qml"
    for path, content in ((main_qml, QML), (video_qml, VIDEO_BG_QML)):
        try:
            old = path.read_text("utf-8") if path.exists() else None
        except OSError:
            old = None
        if old != content:
            path.write_text(content, "utf-8")
    return main_qml, video_qml


def main_gui_proc(a, ipc_name):
    QGuiApplication, QPixmapCache, QQmlApplicationEngine, Qt, QTimer, QUrl, GuiBridge = _build_gui_runtime()
    app = QGuiApplication(sys.argv)
    app.setApplicationName("qt-music")
    app.setDesktopFileName("qt-music")

    QPixmapCache.setCacheLimit(12 * 1024)
    main_qml, video_qml = _write_cached_qml()

    bridge = GuiBridge(a, ipc_name)
    bridge._cfg["videoQml"] = _uri_from_path(video_qml)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("bridge", bridge)
    engine.load(QUrl.fromLocalFile(str(main_qml)))
    if not engine.rootObjects():
        sys.exit("could not load the UI - is Qt Quick complete? (sudo pacman -S pyside6 qt6-declarative)")
    win = engine.rootObjects()[0]
    bridge._win = win
    try:
        win.sceneGraphError.connect(lambda err, msg: print(f"qt-music: sceneGraphError {err}: {msg}", file=sys.stderr))
    except Exception:
        pass

    if a.windowed:
        win.showNormal()
    else:
        win.showFullScreen()
    win.raise_()
    win.requestActivate()

    if not a.screenshot and not a.windowed:
        try:
            wid = int(win.winId())
            if wid:
                subprocess.Popen(
                    ["xprop", "-id", str(wid), "-f", "_NET_WM_BYPASS_COMPOSITOR", "32c", "-set", "_NET_WM_BYPASS_COMPOSITOR", "1"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
        except Exception:
            pass

    if a.size:
        win.resize(*[int(v) for v in a.size.lower().split("x")])

    steps = [s for s in (a.keys or "").split(",") if s]
    if steps:
        from PySide6.QtTest import QTest
        def press(i=0):
            if i >= len(steps): return
            mods, name = Qt.KeyboardModifier.NoModifier, steps[i]
            while "+" in name[1:]:
                m, name = name.split("+", 1)
                mods |= {"Shift": Qt.KeyboardModifier.ShiftModifier, "Ctrl": Qt.KeyboardModifier.ControlModifier}[m]
            if name.startswith("wait"):
                QTimer.singleShot(int(name[4:] or 500), lambda: press(i + 1))
                return
            if len(name) == 1: QTest.keyClick(win, name, mods)
            else: QTest.keyClick(win, getattr(Qt.Key, "Key_" + name), mods)
            QTimer.singleShot(350, lambda: press(i + 1))
        QTimer.singleShot(1200, press)
    if a.screenshot:
        total = sum(int(s[4:] or 500) if s.startswith("wait") else 350 for s in steps)
        QTimer.singleShot(2000 + total, lambda: (win.grabWindow().save(a.screenshot), bridge.quitApp()))

    sys.exit(app.exec())


