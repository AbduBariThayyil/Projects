#!/usr/bin/env python3
import sys
import os
import time
import socket
import logging
import threading
import select
import termios
import tty
import urllib.parse
import http.server
import socketserver
import json
import signal
import atexit
import bisect
import requests
import requests.adapters
import pychromecast

# Silence all pychromecast, urllib3, and zeroconf internal logging
for logger_name in [
    "pychromecast",
    "pychromecast.socket_client",
    "pychromecast.discovery",
    "pychromecast.controllers",
    "zeroconf",
    "urllib3",
]:
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

DEFAULT_PORT = 8765
STATE_DIR = os.path.expanduser("~/.local/state/omniview")
LEGACY_STATE_DIR = os.path.expanduser("~/.local/state/ani-cast")
RESUME_FILE = os.path.join(STATE_DIR, "resume_state.json")
LEGACY_RESUME_FILE = os.path.join(LEGACY_STATE_DIR, "resume_state.json")
SESSION_DEVICE_FILE = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "omniview_session_device")
ACTION_FILE = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "omniview_action")
LEGACY_ACTION_FILE = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "ani_cast_action")
DEVICES_CACHE_FILE = os.path.join(STATE_DIR, "discovered_devices.json")
LEGACY_DEVICES_CACHE_FILE = os.path.join(LEGACY_STATE_DIR, "discovered_devices.json")

def find_free_port(start_port=8765):
    """Find an available port starting from start_port."""
    for p in range(start_port, start_port + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", p))
                return p
            except OSError:
                continue
    return start_port

def normalize_title(t):
    if not t:
        return ""
    return " ".join(t.strip().lower().split())

def load_all_resume_state():
    state = {}
    try:
        if os.path.exists(LEGACY_RESUME_FILE):
            with open(LEGACY_RESUME_FILE, "r", encoding="utf-8") as f:
                state.update(json.load(f))
    except Exception:
        pass
    try:
        if os.path.exists(RESUME_FILE):
            with open(RESUME_FILE, "r", encoding="utf-8") as f:
                state.update(json.load(f))
    except Exception:
        pass
    return state

def save_resume_state(title, position, duration=0.0, finished=False):
    """Atomically save resume state for the given title."""
    if not title:
        return
    try:
        os.makedirs(os.path.dirname(RESUME_FILE), exist_ok=True)
        data = load_all_resume_state()
        data[title.strip()] = {
            "title": title.strip(),
            "position": round(max(0.0, position), 1),
            "duration": round(duration, 1) if duration else 0.0,
            "finished": bool(finished),
            "updated_at": int(time.time()),
        }
        temp_file = f"{RESUME_FILE}.tmp.{os.getpid()}"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(temp_file, RESUME_FILE)
    except Exception:
        pass

def get_saved_position(title):
    """Returns saved position in seconds, or 0.0 if not found or already finished."""
    if not title:
        return 0.0
    state = load_all_resume_state()
    norm = normalize_title(title)
    for k, v in state.items():
        if normalize_title(k) == norm:
            if not v.get("finished", False):
                pos = float(v.get("position", 0.0))
                dur = float(v.get("duration", 0.0))
                if dur > 0 and pos >= (dur - 25.0):
                    return 0.0
                return pos
            return 0.0
    return 0.0

def get_session_device():
    try:
        if os.path.exists(SESSION_DEVICE_FILE):
            with open(SESSION_DEVICE_FILE, "r", encoding="utf-8") as f:
                d = f.read().strip()
                if d:
                    return d
    except Exception:
        pass
    return None

def save_session_device(device_name):
    if not device_name:
        return
    try:
        with open(SESSION_DEVICE_FILE, "w", encoding="utf-8") as f:
            f.write(device_name.strip() + "\n")
    except Exception:
        pass

def parse_time_str(time_str):
    if not time_str:
        return 0.0
    s = str(time_str).strip().lower().rstrip("s")
    if s.endswith("m") or s.endswith("min") or s.endswith("mins"):
        try:
            val = float(s.replace("mins", "").replace("min", "").replace("m", ""))
            return val * 60.0
        except Exception:
            pass
    try:
        parts = [float(p) for p in s.split(":")]
        if len(parts) == 1:
            return parts[0]
        elif len(parts) == 2:
            return parts[0] * 60 + parts[1]
        elif len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
    except Exception:
        pass
    return 0.0

def format_time(seconds):
    if not seconds or seconds < 0:
        return "00:00"
    s = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def render_bar(pos, duration, is_playing, vol, is_muted, width=28):
    state_icon = "\033[1;32m▶\033[0m" if is_playing else "\033[1;33m⏸\033[0m"
    pos_str = format_time(pos)
    dur_str = format_time(duration) if duration and duration > 0 else "--:--"

    pct = 0.0
    if duration and duration > 0:
        pct = max(0.0, min(1.0, pos / duration))

    filled = int(pct * width)
    if filled >= width:
        bar = "━" * width
    elif filled > 0:
        bar = "━" * (filled - 1) + "╸" + "─" * (width - filled)
    else:
        bar = "─" * width

    pct_str = f"{int(pct * 100):2d}%"
    vol_str = "\033[1;31mMUTED\033[0m" if is_muted else f"{int((vol or 0) * 100)}%"

    return f" {state_icon} \033[1;36m[{pos_str} / {dur_str}]\033[0m [\033[1;34m{bar}\033[0m] \033[1;37m{pct_str}\033[0m | \033[1;33mVol: {vol_str}\033[0m"

def get_local_ip(target_ip):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((target_ip, 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()

REFERER = ""
M3U8_URL = ""
SUB_FILE = ""
TITLE = ""
m3u8_content = b""
segment_buffer = None

class KeyboardController:
    """Non-blocking keyboard listener using cbreak mode for laptop-based controls."""
    def __init__(self):
        self.fd = None
        self.old_settings = None
        self.tty_file = None

    def start(self):
        try:
            if sys.stdin.isatty():
                self.fd = sys.stdin.fileno()
            else:
                self.tty_file = open("/dev/tty", "r")
                self.fd = self.tty_file.fileno()
            self.old_settings = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
        except Exception:
            self.fd = None

    def stop(self):
        if self.fd is not None and self.old_settings is not None:
            try:
                termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)
            except Exception:
                pass
            self.fd = None
        if self.tty_file:
            try:
                self.tty_file.close()
            except Exception:
                pass
            self.tty_file = None

    def read_command(self, timeout=0.25):
        if self.fd is None:
            time.sleep(timeout)
            return None
        try:
            r, _, _ = select.select([self.fd], [], [], timeout)
            if not r:
                return None
            data = os.read(self.fd, 32)
            if not data:
                return None
            raw = data.decode("utf-8", errors="ignore")
            return self._decode(raw)
        except Exception:
            return None

    def _decode(self, raw):
        if raw in [" ", "p", "P"]:
            return "pause"
        elif raw in ["\x1b[D", "\x1bOD", "h", "H", ",", "<"]:
            return "seek_back"
        elif raw in ["\x1b[C", "\x1bOC", "l", "L", ".", ">"]:
            return "seek_fwd"
        elif raw in ["["]:
            return "seek_back_30"
        elif raw in ["]"]:
            return "seek_fwd_30"
        elif raw in ["{", "\x1b[1;5D"]:
            return "seek_back_60"
        elif raw in ["}", "\x1b[1;5C"]:
            return "seek_fwd_60"
        elif raw in ["\x1b[A", "\x1bOA", "k", "K", "+", "=", "0"]:
            return "vol_up"
        elif raw in ["\x1b[B", "\x1bOB", "j", "J", "-", "9"]:
            return "vol_down"
        elif raw in ["m", "M"]:
            return "mute"
        elif raw in ["n", "N"]:
            return "next"
        elif raw in ["q", "Q", "\x03"]:
            return "quit"
        return None

class SegmentBuffer:
    """
    Intelligent lookahead pre-fetcher and memory ring buffer.
    Buffers 36 segments ahead (~2.5 minutes) with 6 parallel workers, connection pooling, deduplication, and condition variables.
    """
    def __init__(self, session, referer, lookahead=36, lookbehind=10):
        self.session = session
        self.referer = referer
        self.lookahead = lookahead
        self.lookbehind = lookbehind
        self.segments = []      # List of target URLs in sequential order
        self.cache = {}         # idx -> bytes
        self.in_progress = set()
        self.failed_counts = {}
        self.lock = threading.Lock()
        self.cond = threading.Condition(self.lock)
        self.last_requested_idx = 0
        self.running = True

    def set_segments(self, seg_urls, start_idx=0):
        with self.lock:
            self.segments = seg_urls
            self.last_requested_idx = start_idx
            self.failed_counts.clear()
            self.cond.notify_all()

    def seek(self, new_idx):
        with self.lock:
            self.last_requested_idx = new_idx
            self.in_progress.clear()
            self.cond.notify_all()

    def get_segment(self, idx, target_url):
        with self.lock:
            self.last_requested_idx = idx
            self.cond.notify_all()  # Wake up prefetch workers to push buffer frontier forward
            if idx in self.cache:
                return self.cache[idx]

            # If already downloading in background worker, wait cleanly on condition variable
            if idx in self.in_progress:
                start_wait = time.time()
                while idx in self.in_progress and (time.time() - start_wait < 15.0):
                    self.cond.wait(timeout=0.15)
                if idx in self.cache:
                    return self.cache[idx]

            # Cache miss: claim it so no worker downloads the same segment in duplicate
            self.in_progress.add(idx)

        data = self._fetch(target_url)
        with self.lock:
            self.in_progress.discard(idx)
            if data:
                self.cache[idx] = data
                self._prune(idx)
            self.cond.notify_all()
        return data

    def _fetch(self, url):
        headers = {
            "Referer": self.referer,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Connection": "keep-alive",
        }
        for attempt in range(4):
            try:
                resp = self.session.get(url, headers=headers, timeout=(4.0, 12.0))
                if resp.status_code == 200 and resp.content:
                    return resp.content
            except Exception:
                pass
            time.sleep(0.08 * (attempt + 1))
        return None

    def _prune(self, current_idx):
        min_keep = max(0, current_idx - self.lookbehind)
        max_keep = current_idx + self.lookahead + 16
        to_del = [i for i in self.cache if i < min_keep or i > max_keep]
        for i in to_del:
            del self.cache[i]

    def worker_loop(self):
        while self.running:
            target_to_fetch = None
            target_idx = None

            with self.lock:
                if self.segments:
                    start = self.last_requested_idx
                    end = min(len(self.segments), start + self.lookahead + 1)
                    for i in range(start, end):
                        if (i not in self.cache and 
                            i not in self.in_progress and 
                            self.failed_counts.get(i, 0) < 4):
                            target_idx = i
                            target_to_fetch = self.segments[i]
                            self.in_progress.add(i)
                            break

            if target_to_fetch:
                data = self._fetch(target_to_fetch)
                with self.lock:
                    self.in_progress.discard(target_idx)
                    if data:
                        self.cache[target_idx] = data
                        self._prune(self.last_requested_idx)
                    else:
                        self.failed_counts[target_idx] = self.failed_counts.get(target_idx, 0) + 1
                    self.cond.notify_all()
                if not data:
                    time.sleep(0.1)
            else:
                with self.cond:
                    self.cond.wait(timeout=0.25)

    def prewarm(self, count=8, timeout=4.0):
        """Pre-buffers initial segments so Chromecast begins playback with instant zero-latency cache."""
        t0 = time.time()
        while time.time() - t0 < timeout:
            with self.lock:
                start = self.last_requested_idx
                end = min(len(self.segments), start + count)
                if end > start:
                    cached = sum(1 for i in range(start, end) if i in self.cache)
                    if cached >= min(count, end - start):
                        return True
            time.sleep(0.08)
        return False

    def stop(self):
        self.running = False
        with self.lock:
            self.cond.notify_all()

class HLSProxyHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_OPTIONS(self):
        try:
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
            self.send_header("Connection", "keep-alive")
            self.send_header("Content-Length", "0")
            self.end_headers()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, socket.error):
            pass

    def do_HEAD(self):
        self.handle_request(head_only=True)

    def do_GET(self):
        self.handle_request(head_only=False)

    def handle_request(self, head_only=False):
        try:
            if self.path.startswith("/playlist.m3u8"):
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Headers", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
                self.send_header("Connection", "keep-alive")
                self.send_header("Keep-Alive", "timeout=60, max=1000")
                self.send_header("Content-Length", str(len(m3u8_content)))
                self.end_headers()
                if not head_only:
                    self.wfile.write(m3u8_content)
                    self.wfile.flush()

            elif "/seg_" in self.path:
                parsed = urllib.parse.urlparse(self.path)
                qs = urllib.parse.parse_qs(parsed.query)
                if "u" not in qs:
                    try:
                        self.send_error(400)
                    except Exception:
                        pass
                    return

                target_url = qs["u"][0]

                seg_idx = 0
                try:
                    seg_name = self.path.split("/seg_")[1].split(".ts")[0]
                    seg_idx = int(seg_name)
                except Exception:
                    pass

                data = segment_buffer.get_segment(seg_idx, target_url) if segment_buffer else None

                if not data:
                    try:
                        self.send_error(502)
                    except Exception:
                        pass
                    return

                total_len = len(data)
                range_header = self.headers.get("Range")
                status_code = 200
                start_byte = 0
                end_byte = total_len - 1

                if range_header and range_header.startswith("bytes="):
                    try:
                        parts = range_header[6:].split("-")
                        if parts[0]:
                            start_byte = int(parts[0])
                        if len(parts) > 1 and parts[1]:
                            end_byte = int(parts[1])
                        if start_byte < total_len:
                            end_byte = min(end_byte, total_len - 1)
                            status_code = 206
                    except Exception:
                        start_byte = 0
                        end_byte = total_len - 1
                        status_code = 200

                body = data[start_byte:end_byte + 1] if not head_only else b""

                try:
                    self.send_response(status_code)
                    self.send_header("Content-Type", "video/mp2t")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Access-Control-Allow-Headers", "*")
                    self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
                    self.send_header("Accept-Ranges", "bytes")
                    if status_code == 206:
                        self.send_header("Content-Range", f"bytes {start_byte}-{end_byte}/{total_len}")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Connection", "keep-alive")
                    self.send_header("Keep-Alive", "timeout=60, max=1000")
                    self.end_headers()

                    if not head_only and body:
                        self.wfile.write(body)
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, socket.error):
                    return

            elif self.path.startswith("/subtitles.vtt") and SUB_FILE and os.path.exists(SUB_FILE):
                try:
                    with open(SUB_FILE, "rb") as f:
                        sub_data = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/vtt; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Access-Control-Allow-Headers", "*")
                    self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
                    self.send_header("Connection", "keep-alive")
                    self.send_header("Keep-Alive", "timeout=60, max=1000")
                    self.send_header("Content-Length", str(len(sub_data)))
                    self.end_headers()
                    if not head_only:
                        self.wfile.write(sub_data)
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, socket.error):
                    return
                except Exception:
                    try:
                        self.send_error(500)
                    except Exception:
                        pass
            else:
                try:
                    self.send_error(404)
                except Exception:
                    pass
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, socket.error):
            return

    def log_message(self, format, *args):
        pass

class ThreadedServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 64

    def handle_error(self, request, client_address):
        exc_type, exc_val, exc_tb = sys.exc_info()
        if exc_type and issubclass(exc_type, (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, socket.error, OSError)):
            return

def load_cached_devices():
    """Load previously discovered devices from disk cache."""
    try:
        if os.path.exists(DEVICES_CACHE_FILE):
            with open(DEVICES_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []

def save_cached_devices(devices):
    """Save discovered devices to disk cache."""
    try:
        os.makedirs(os.path.dirname(DEVICES_CACHE_FILE), exist_ok=True)
        with open(DEVICES_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(devices, f, indent=2)
    except Exception:
        pass

def scan_cast_devices(timeout=2.5):
    """Dynamically scans local network via mDNS for any Google Cast / Android TV devices."""
    import zeroconf
    from pychromecast.discovery import CastBrowser, SimpleCastListener

    discovered = []
    seen_hosts = set()

    def add_cb(uuid, service):
        dev = browser.devices.get(uuid)
        if dev and dev.host and dev.host not in seen_hosts:
            seen_hosts.add(dev.host)
            discovered.append({
                "name": dev.friendly_name or "TV",
                "ip": dev.host,
                "port": dev.port or 8009,
                "model": dev.model_name or "Cast Device",
            })

    try:
        zconf = zeroconf.Zeroconf()
        browser = CastBrowser(SimpleCastListener(add_cb), zconf)
        browser.start_discovery()
        t_start = time.time()
        while time.time() - t_start < timeout:
            time.sleep(0.15)
            # If at least 1 device is found, give 1.5s total then finish quickly
            if discovered and (time.time() - t_start >= 1.5):
                break
        browser.stop_discovery()
        zconf.close()
    except Exception:
        pass

    return discovered

class LocalMediaStatus:
    def __init__(self):
        self.player_is_playing = True
        self.player_is_paused = False
        self.player_state = "PLAYING"
        self.current_time = 0.0
        self.adjusted_current_time = 0.0
        self.duration = 0.0
        self.idle_reason = None

class LocalMediaController:
    def __init__(self, sock_path):
        self.sock_path = sock_path
        self.status = LocalMediaStatus()
        self.sock = None
        self._lock = threading.Lock()

    def _send_cmd(self, cmd_list):
        with self._lock:
            try:
                if not self.sock:
                    if os.path.exists(self.sock_path):
                        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                        self.sock.settimeout(0.5)
                        self.sock.connect(self.sock_path)
                if self.sock:
                    msg = json.dumps({"command": cmd_list}) + "\n"
                    self.sock.sendall(msg.encode("utf-8"))
                    resp = self.sock.recv(4096).decode("utf-8", errors="ignore")
                    if resp:
                        for line in resp.splitlines():
                            try:
                                d = json.loads(line)
                                if "data" in d:
                                    return d["data"]
                            except Exception:
                                pass
            except Exception:
                try:
                    if self.sock:
                        self.sock.close()
                except Exception:
                    pass
                self.sock = None
        return None

    def update_status(self):
        cur = self._send_cmd(["get_property", "time-pos"])
        dur = self._send_cmd(["get_property", "duration"])
        paused = self._send_cmd(["get_property", "pause"])

        if cur is not None and isinstance(cur, (int, float)):
            self.status.current_time = float(cur)
            self.status.adjusted_current_time = float(cur)
        if dur is not None and isinstance(dur, (int, float)):
            self.status.duration = float(dur)
        if paused is not None:
            self.status.player_is_paused = bool(paused)
            self.status.player_is_playing = not bool(paused)
            self.status.player_state = "PAUSED" if bool(paused) else "PLAYING"

    def play(self):
        self._send_cmd(["set_property", "pause", False])
        self.status.player_is_paused = False
        self.status.player_is_playing = True
        self.status.player_state = "PLAYING"

    def pause(self):
        self._send_cmd(["set_property", "pause", True])
        self.status.player_is_paused = True
        self.status.player_is_playing = False
        self.status.player_state = "PAUSED"

    def seek(self, target):
        self._send_cmd(["seek", float(target), "absolute"])
        self.status.current_time = float(target)

    def stop(self):
        self._send_cmd(["quit"])
        self.status.player_state = "IDLE"

class LocalPlayerController:
    def __init__(self):
        self.name = "This Device (Local Screen / MPV)"
        self.is_local = True
        self.cast_info = type("CastInfo", (), {"host": "127.0.0.1"})()
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
        self.ipc_sock = os.path.join(runtime_dir, f"ani_cast_mpv_sock_{os.getpid()}")
        self.media_controller = LocalMediaController(self.ipc_sock)
        self.mpv_proc = None
        self.status = type("CastStatus", (), {"volume_level": 0.8, "volume_muted": False})()
        self.is_connected = True
        atexit.register(self.disconnect)

    def start_playback(self, video_url, sub_url, title, current_time=0.0):
        if os.path.exists(self.ipc_sock):
            try:
                os.remove(self.ipc_sock)
            except Exception:
                pass

        cmd = [
            "mpv",
            video_url,
            f"--input-ipc-server={self.ipc_sock}",
            f"--force-media-title={title}",
            "--msg-level=all=no",
        ]
        if current_time and float(current_time) > 0:
            cmd.append(f"--start={float(current_time)}")
        if sub_url:
            cmd.append(f"--sub-file={sub_url}")

        self.mpv_proc = subprocess.Popen(cmd)
        for _ in range(30):
            time.sleep(0.1)
            if os.path.exists(self.ipc_sock):
                break
        return self.media_controller

    def set_volume(self, level):
        lvl = max(0.0, min(1.0, float(level)))
        self.status.volume_level = lvl
        self.media_controller._send_cmd(["set_property", "volume", lvl * 100])

    def set_volume_muted(self, muted):
        self.status.volume_muted = bool(muted)
        self.media_controller._send_cmd(["set_property", "mute", bool(muted)])

    def disconnect(self):
        if self.mpv_proc:
            try:
                self.mpv_proc.terminate()
            except Exception:
                pass
            self.mpv_proc = None
        if os.path.exists(self.ipc_sock):
            try:
                os.remove(self.ipc_sock)
            except Exception:
                pass

def connect_chromecast_direct(ip, name="TV", timeout=2.5):
    """Directly connects to a Chromecast by IP without mDNS overhead (0.3s)."""
    try:
        cast = pychromecast.get_chromecast_from_host((ip, 8009, None, None, name), timeout=timeout)
        cast.wait(timeout=timeout)
        return cast
    except Exception:
        return None

def discover_chromecast(silent=False, target_device=None):
    target_pref = target_device or os.environ.get("ANI_CAST_DEVICE", "").strip()

    # Direct local requested via flag or env
    if os.environ.get("ANI_CAST_LOCAL") == "1" or target_pref.lower() in ["local", "0", "this", "screen", "pc", "laptop"]:
        save_session_device("This Device|127.0.0.1")
        return LocalPlayerController()

    # 1. Continuous streaming session: reuse previously selected session device
    if not target_device:
        session_d = get_session_device()
        if session_d:
            parts = session_d.split("|")
            dev_name = parts[0]
            dev_ip = parts[1] if len(parts) > 1 else ""
            if dev_ip == "127.0.0.1" or "this device" in dev_name.lower():
                return LocalPlayerController()
            if dev_ip:
                cast = connect_chromecast_direct(dev_ip, dev_name, timeout=2.0)
                if cast:
                    return cast
            if not target_pref:
                target_pref = dev_name

    # 2. Dynamic discovery: scan the local network for all active Cast devices
    if not silent:
        print("\033[1;36m==>\033[0m Scanning local network for TV / Chromecast devices...", flush=True)

    devices = scan_cast_devices(timeout=2.5)

    # Fallback to previously cached devices if mDNS was slow or missed
    cached_devices = load_cached_devices()
    if not devices and cached_devices:
        for d in cached_devices:
            if connect_chromecast_direct(d["ip"], d["name"], timeout=0.8):
                devices.append(d)

    # Update cache with newly discovered devices
    if devices:
        merged = {d["name"]: d for d in (cached_devices + devices)}
        save_cached_devices(list(merged.values()))

    # If no devices discovered on Wi-Fi, automatically fallback to local playback
    if not devices:
        if not silent:
            print("\033[1;33m[!] No TV / Chromecast discovered on Wi-Fi. Playing locally on this device...\033[0m")
        save_session_device("This Device|127.0.0.1")
        return LocalPlayerController()

    chosen_info = None

    # 3. If target was explicitly specified (via -t, --device, or env):
    if target_pref:
        if target_pref.lower() in ["local", "0", "this", "screen", "pc", "laptop"]:
            save_session_device("This Device|127.0.0.1")
            return LocalPlayerController()
        elif target_pref.isdigit():
            idx = int(target_pref)
            if idx == 0:
                save_session_device("This Device|127.0.0.1")
                return LocalPlayerController()
            elif 1 <= idx <= len(devices):
                chosen_info = devices[idx - 1]
            else:
                chosen_info = devices[0]
        else:
            for d in devices:
                if target_pref.lower() in d["name"].lower() or target_pref == d["ip"]:
                    chosen_info = d
                    break
            if not chosen_info:
                # If target_pref is an explicit IP, try direct connect
                chosen_info = {"name": target_pref, "ip": target_pref, "port": 8009}

    # 4. If no target specified (fresh command): Interactive selection
    if not chosen_info:
        if not silent:
            print("\n\033[1;35m[?] Select Playback Target:\033[0m")
            print("  \033[1;36m0)\033[0m This Device (Local Screen / MPV)")
            for idx, dev in enumerate(devices, 1):
                default_tag = " \033[1;32m(Default)\033[0m" if idx == 1 else ""
                print(f"  \033[1;36m{idx})\033[0m {dev['name']} ({dev['ip']}) [{dev.get('model', 'Cast')}]{default_tag}")

            prompt_msg = f"\033[1;33mSelect device [0-{len(devices)}, Enter for 1]: \033[0m"
            choice = ""
            try:
                if sys.stdin.isatty():
                    choice = input(prompt_msg).strip()
                else:
                    with open("/dev/tty", "r") as tty_in:
                        print(prompt_msg, end="", flush=True)
                        choice = tty_in.readline().strip()
            except Exception:
                choice = "1"

            if choice in ["0", "l", "local", "this"]:
                save_session_device("This Device|127.0.0.1")
                return LocalPlayerController()
            elif choice.isdigit() and 1 <= int(choice) <= len(devices):
                chosen_info = devices[int(choice) - 1]
            else:
                chosen_info = devices[0]
            print(f"\033[1;32m==>\033[0m Selected: {chosen_info['name']}\n", flush=True)
        else:
            chosen_info = devices[0]

    # 5. Connect directly to selected device
    save_session_device(f"{chosen_info['name']}|{chosen_info['ip']}")
    if chosen_info.get("ip") == "127.0.0.1":
        return LocalPlayerController()
    if not silent:
        print(f"\033[1;36m==>\033[0m Connecting to {chosen_info['name']} ({chosen_info['ip']})...", flush=True)
    cast = connect_chromecast_direct(chosen_info["ip"], chosen_info["name"], timeout=3.5)
    return cast

def parse_and_rewrite_m3u8(raw_m3u8, local_ip, port, m3u8_url):
    rewritten_lines = []
    seg_urls = []
    seg_start_times = []
    current_time = 0.0
    pending_duration = None
    seg_idx = 0

    for line in raw_m3u8.splitlines():
        stripped = line.strip()
        if stripped.startswith("#EXTINF:"):
            try:
                val = stripped.split(":")[1].split(",")[0]
                pending_duration = float(val)
            except Exception:
                pending_duration = 4.0
            rewritten_lines.append(line)
        elif stripped and not stripped.startswith("#"):
            abs_url = urllib.parse.urljoin(m3u8_url, stripped)
            seg_urls.append(abs_url)
            seg_start_times.append(current_time)
            if pending_duration is not None:
                current_time += pending_duration
                pending_duration = None
            else:
                current_time += 4.0
            encoded = urllib.parse.quote(abs_url)
            rewritten_lines.append(f"http://{local_ip}:{port}/seg_{seg_idx:05d}.ts?u={encoded}")
            seg_idx += 1
        else:
            rewritten_lines.append(line)

    manifest_bytes = "\n".join(rewritten_lines).encode("utf-8")
    total_manifest_duration = current_time
    return manifest_bytes, seg_urls, seg_start_times, total_manifest_duration

def find_segment_index(seg_start_times, target_time):
    """Accurately binary searches the segment index for any timestamp."""
    if not seg_start_times or target_time <= 0:
        return 0
    idx = bisect.bisect_right(seg_start_times, target_time) - 1
    return max(0, min(len(seg_start_times) - 1, idx))

def start_playback_on_cast(cast, video_url, sub_url, title, current_time=0.0):
    if getattr(cast, "is_local", False):
        return cast.start_playback(video_url, sub_url, title, current_time=current_time)

    if cast.app_id != "CC1AD845":
        try:
            cast.start_app("CC1AD845", timeout=15.0)
        except Exception:
            time.sleep(1)

    mc = cast.media_controller

    try:
        mc.stop()
        time.sleep(0.3)
    except Exception:
        pass

    media_kwargs = {
        "content_type": "application/vnd.apple.mpegurl",
        "title": title,
        "stream_type": "BUFFERED",
        "autoplay": True,
    }
    if current_time and float(current_time) > 0:
        media_kwargs["current_time"] = float(current_time)

    if sub_url:
        media_kwargs.update({
            "subtitles": sub_url,
            "subtitles_mime": "text/vtt",
            "subtitles_lang": "en-US",
        })

    mc.play_media(video_url, **media_kwargs)
    mc.block_until_active(timeout=10)
    time.sleep(0.5)

    try:
        mc.play()
    except Exception:
        pass

    if sub_url:
        time.sleep(0.8)
        try:
            mc.enable_subtitle(1)
        except Exception:
            pass

    return mc

def main():
    global REFERER, M3U8_URL, SUB_FILE, TITLE, m3u8_content, segment_buffer

    if len(sys.argv) < 3:
        print("Usage: hls_streamer.py <referer> <m3u8_url> [sub_file] [title] [start_time]")
        sys.exit(1)

    REFERER = sys.argv[1]
    M3U8_URL = sys.argv[2]
    SUB_FILE = sys.argv[3] if len(sys.argv) > 3 else ""
    TITLE = sys.argv[4] if len(sys.argv) > 4 else "Anime Episode"

    # Setup persistent HTTP session with connection pooling
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=35, pool_maxsize=35, max_retries=3)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    segment_buffer = SegmentBuffer(session, REFERER, lookahead=36, lookbehind=10)

    # 1. Discover TV (prompts for TV 1 or 2 on initial launch)
    cast = None
    while not cast:
        cast = discover_chromecast(silent=False)
        if not cast:
            print("\033[1;33m[!] TV not responding yet. Retrying in 2 seconds... (Press Ctrl+C to cancel)\033[0m", flush=True)
            try:
                time.sleep(2)
            except KeyboardInterrupt:
                print("\n[*] Cancelled.", flush=True)
                sys.exit(0)

    device_name = cast.name or "TV"
    device_ip = cast.cast_info.host if cast.cast_info else "127.0.0.1"
    print(f"\033[1;32m==>\033[0m Connected to {device_name} ({device_ip})", flush=True)

    local_ip = get_local_ip(device_ip)
    port = find_free_port(DEFAULT_PORT)

    # 2. Fetch master stream playlist
    print(f"\033[1;36m==>\033[0m Connecting to stream: {TITLE}...", flush=True)
    req_headers = {"Referer": REFERER, "User-Agent": "Mozilla/5.0"}
    resp = session.get(M3U8_URL, headers=req_headers, timeout=15)
    raw_m3u8 = resp.text

    m3u8_content, seg_urls, seg_start_times, total_manifest_duration = parse_and_rewrite_m3u8(
        raw_m3u8, local_ip, port, M3U8_URL
    )

    # 3. Determine start time: explicit command-line argument vs auto-resume
    explicit_time_str = os.environ.get("ANI_CAST_START_TIME")
    if len(sys.argv) > 5 and sys.argv[5]:
        explicit_time_str = sys.argv[5]

    is_explicit = explicit_time_str is not None and explicit_time_str.strip() != ""

    if is_explicit:
        initial_time = parse_time_str(explicit_time_str)
        resumed_from_saved = False
    else:
        saved_pos = get_saved_position(TITLE)
        if saved_pos > 5.0:
            initial_time = max(0.0, saved_pos - 2.0)
            resumed_from_saved = True
        else:
            initial_time = 0.0
            resumed_from_saved = False

    # Accurate start segment lookup
    start_seg_idx = find_segment_index(seg_start_times, initial_time)
    segment_buffer.set_segments(seg_urls, start_idx=start_seg_idx)

    # Launch 6 parallel pre-fetch threads to maximize CDN throughput without congestion
    for _ in range(6):
        prefetch_t = threading.Thread(target=segment_buffer.worker_loop, daemon=True)
        prefetch_t.start()

    # Pre-buffer first 6 segments so Chromecast receives instant stream responses
    segment_buffer.prewarm(count=6, timeout=3.5)

    # 4. Start local proxy server in background thread
    socketserver.TCPServer.allow_reuse_address = True
    httpd = ThreadedServer(("0.0.0.0", port), HLSProxyHandler)
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    has_subs = bool(SUB_FILE and os.path.exists(SUB_FILE) and os.path.getsize(SUB_FILE) > 0)
    video_url = f"http://{local_ip}:{port}/playlist.m3u8"
    sub_url = f"http://{local_ip}:{port}/subtitles.vtt" if has_subs else None

    # 5. Start playback
    if initial_time > 0:
        imins = int(initial_time // 60)
        isecs = int(initial_time % 60)
        if resumed_from_saved:
            print(f"\033[1;32m==>\033[0m Found saved progress: Resuming {TITLE} from {imins:02d}:{isecs:02d}...", flush=True)
        else:
            print(f"\033[1;32m==>\033[0m Jumping directly to {imins:02d}:{isecs:02d}...", flush=True)
    else:
        print(f"\033[1;32m==>\033[0m Streaming directly to TV (Instant Playback, 0s wait)...", flush=True)

    mc = start_playback_on_cast(cast, video_url, sub_url, TITLE, current_time=initial_time)

    # Check if this episode is the final episode of its season
    is_season_finale = False
    try:
        lib_dir = os.path.dirname(os.path.abspath(__file__))
        if lib_dir not in sys.path:
            sys.path.insert(0, lib_dir)
        from anicast_engine import parse_anime_title, get_episodes, search_anime
        anime_base, s_num, ep_num = parse_anime_title(TITLE)
        s_q = f"{anime_base} Season {s_num}" if s_num > 1 else anime_base
        s_res = search_anime(s_q)
        if s_res:
            all_eps = get_episodes(s_res[0]["slug"])
            if all_eps and ep_num >= len(all_eps):
                is_season_finale = True
    except Exception:
        pass

    is_local = getattr(cast, "is_local", False)
    if is_local:
        print(f"\033[1;32m[+] Playing locally on this device (MPV)!\033[0m", flush=True)
        banner_title = "Local Playback Controls (MPV window or keyboard here):"
    else:
        print(f"[+] Playing on {device_name}!", flush=True)
        banner_title = "Remote-Free Controls:                                 "

    next_btn_label = "[n] Stream Next Season" if is_season_finale else "[n] Stream Next Ep    "

    # 6. Remote-Free Controls cheatsheet & live progress bar
    print("\n\033[1;35m┌────────────────────────────────────────────────────────────────────────┐\033[0m")
    print(f"\033[1;35m│\033[0m  \033[1;37m{banner_title}\033[0m       \033[1;35m│\033[0m")
    print("\033[1;35m│\033[0m   \033[1;36m[Space/p]\033[0m Pause/Play    \033[1;36m[← / →]\033[0m Seek ±10s    \033[1;36m[↑ / ↓]\033[0m Vol ±5% (0/9) \033[1;35m│\033[0m")
    print(f"\033[1;35m│\033[0m   \033[1;36m[[ / ]]\033[0m   Seek ±30s     \033[1;36m[m]\033[0m Mute/Unmute      \033[1;36m{next_btn_label}\033[0m \033[1;35m│\033[0m")
    print("\033[1;35m│\033[0m   \033[1;36m[q]\033[0m      Stop & Quit (saves progress, exits to shell)         \033[1;35m│\033[0m")
    print("\033[1;35m└────────────────────────────────────────────────────────────────────────┘\033[0m\n")

    kbd = KeyboardController()
    kbd.start()

    # Hide terminal cursor for clean progress bar presentation
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    def cleanup_terminal():
        sys.stdout.write("\033[?25h\n")
        sys.stdout.flush()
        if kbd:
            kbd.stop()

    atexit.register(cleanup_terminal)

    last_known_position = initial_time
    is_finished = False
    chosen_device_name = device_name
    is_paused = False
    current_vol = getattr(cast.status, "volume_level", 0.5) if cast.status else 0.5
    is_muted = getattr(cast.status, "volume_muted", False) if cast.status else False
    duration = total_manifest_duration or 0.0

    status_message = ""
    status_msg_expires = 0.0
    last_save_time = time.time()
    startup_time = time.time()
    idle_counter = 0
    disconnect_counter = 0

    exiting_lock = threading.Lock()
    has_exited = False

    def handle_exit(reason="quit"):
        """
        Unified exit handler:
        - 'quit' / 'sigint': Saves progress, stops TV, restores terminal, kills parent ani-cli cleanly so fzf menu does not pop up. Exit code 130.
        - 'finished': Marks episode finished, writes 'auto_next' action so ani-cast-menu auto-streams next episode, leaves parent ani-cli alive. Exit code 0.
        - 'next': Marks episode finished, writes 'next' action so ani-cast-menu immediately streams next episode, leaves parent ani-cli alive. Exit code 0.
        """
        nonlocal has_exited
        with exiting_lock:
            if has_exited:
                return
            has_exited = True

        cleanup_terminal()
        try:
            mc.stop()
        except Exception:
            pass

        try:
            cast.disconnect()
        except Exception:
            pass

        try:
            segment_buffer.stop()
            httpd.shutdown()
            httpd.server_close()
        except Exception:
            pass

        if reason in ["quit", "sigint"]:
            try:
                if os.path.exists(ACTION_FILE):
                    os.remove(ACTION_FILE)
            except Exception:
                pass
            try:
                if os.path.exists(LEGACY_ACTION_FILE):
                    os.remove(LEGACY_ACTION_FILE)
            except Exception:
                pass
            try:
                if os.path.exists(SESSION_DEVICE_FILE):
                    os.remove(SESSION_DEVICE_FILE)
            except Exception:
                pass

            if last_known_position > 0:
                save_resume_state(TITLE, last_known_position, duration, finished=False)
            mins = int(last_known_position // 60)
            secs = int(last_known_position % 60)
            sys.stdout.write(f"\r\033[K\033[1;33m[*] Playback stopped at {mins:02d}:{secs:02d} (progress saved).\033[0m\n")
            sys.stdout.flush()

            parent_pid = os.getppid()
            if parent_pid > 1:
                try:
                    os.kill(parent_pid, signal.SIGTERM)
                except Exception:
                    pass

            sys.exit(130)

        elif reason == "finished":
            save_resume_state(TITLE, 0.0, duration, finished=True)
            action_val = "auto_next_season" if is_season_finale else "auto_next"
            for a_f in [ACTION_FILE, LEGACY_ACTION_FILE]:
                try:
                    with open(a_f, "w") as f:
                        f.write(action_val + "\n")
                except Exception:
                    pass
            msg = "Season completed!" if is_season_finale else "Episode finished."
            sys.stdout.write(f"\r\033[K\n\033[1;32m[+] {msg}\033[0m\n")
            sys.stdout.flush()
            sys.exit(0)

        elif reason == "next":
            save_resume_state(TITLE, 0.0, duration, finished=True)
            action_val = "next_season" if is_season_finale else "next"
            for a_f in [ACTION_FILE, LEGACY_ACTION_FILE]:
                try:
                    with open(a_f, "w") as f:
                        f.write(action_val + "\n")
                except Exception:
                    pass
            msg = "Advancing to next season..." if is_season_finale else "Advancing to next episode..."
            sys.stdout.write(f"\r\033[K\n\033[1;32m==> {msg}\033[0m\n")
            sys.stdout.flush()
            sys.exit(0)

    def sig_handler(signum, frame):
        handle_exit("sigint")

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    try:
        while not is_finished:
            try:
                # 1. Read keyboard command without blocking
                cmd = kbd.read_command(timeout=0.25)

                if cmd == "quit":
                    handle_exit("quit")
                    return

                elif cmd == "next":
                    handle_exit("next")
                    return

                elif cmd == "pause":
                    if is_paused:
                        try:
                            mc.play()
                            is_paused = False
                            status_message = "\033[1;32m▶ Resumed\033[0m"
                            status_msg_expires = time.time() + 2.0
                        except Exception:
                            pass
                    else:
                        try:
                            mc.pause()
                            is_paused = True
                            status_message = "\033[1;33m⏸ Paused\033[0m"
                            status_msg_expires = time.time() + 2.0
                        except Exception:
                            pass

                elif cmd == "seek_fwd":
                    target_seek = min(duration or (last_known_position + 10.0), last_known_position + 10.0)
                    try:
                        mc.seek(target_seek)
                        last_known_position = target_seek
                        if segment_buffer:
                            seg_idx = find_segment_index(seg_start_times, target_seek)
                            segment_buffer.seek(seg_idx)
                        status_message = f"\033[1;36m⏩ +10s ({format_time(target_seek)})\033[0m"
                        status_msg_expires = time.time() + 2.0
                    except Exception:
                        pass

                elif cmd == "seek_back":
                    target_seek = max(0.0, last_known_position - 10.0)
                    try:
                        mc.seek(target_seek)
                        last_known_position = target_seek
                        if segment_buffer:
                            seg_idx = find_segment_index(seg_start_times, target_seek)
                            segment_buffer.seek(seg_idx)
                        status_message = f"\033[1;36m⏪ -10s ({format_time(target_seek)})\033[0m"
                        status_msg_expires = time.time() + 2.0
                    except Exception:
                        pass

                elif cmd == "seek_fwd_30":
                    target_seek = min(duration or (last_known_position + 30.0), last_known_position + 30.0)
                    try:
                        mc.seek(target_seek)
                        last_known_position = target_seek
                        if segment_buffer:
                            seg_idx = find_segment_index(seg_start_times, target_seek)
                            segment_buffer.seek(seg_idx)
                        status_message = f"\033[1;36m⏩ +30s ({format_time(target_seek)})\033[0m"
                        status_msg_expires = time.time() + 2.0
                    except Exception:
                        pass

                elif cmd == "seek_back_30":
                    target_seek = max(0.0, last_known_position - 30.0)
                    try:
                        mc.seek(target_seek)
                        last_known_position = target_seek
                        if segment_buffer:
                            seg_idx = find_segment_index(seg_start_times, target_seek)
                            segment_buffer.seek(seg_idx)
                        status_message = f"\033[1;36m⏪ -30s ({format_time(target_seek)})\033[0m"
                        status_msg_expires = time.time() + 2.0
                    except Exception:
                        pass

                elif cmd == "seek_fwd_60":
                    target_seek = min(duration or (last_known_position + 60.0), last_known_position + 60.0)
                    try:
                        mc.seek(target_seek)
                        last_known_position = target_seek
                        if segment_buffer:
                            seg_idx = find_segment_index(seg_start_times, target_seek)
                            segment_buffer.seek(seg_idx)
                        status_message = f"\033[1;36m⏩ +60s ({format_time(target_seek)})\033[0m"
                        status_msg_expires = time.time() + 2.0
                    except Exception:
                        pass

                elif cmd == "seek_back_60":
                    target_seek = max(0.0, last_known_position - 60.0)
                    try:
                        mc.seek(target_seek)
                        last_known_position = target_seek
                        if segment_buffer:
                            seg_idx = find_segment_index(seg_start_times, target_seek)
                            segment_buffer.seek(seg_idx)
                        status_message = f"\033[1;36m⏪ -60s ({format_time(target_seek)})\033[0m"
                        status_msg_expires = time.time() + 2.0
                    except Exception:
                        pass

                elif cmd == "vol_up":
                    try:
                        new_vol = min(1.0, current_vol + 0.05)
                        if hasattr(cast, "set_volume"):
                            cast.set_volume(new_vol)
                        elif hasattr(cast, "volume_up"):
                            cast.volume_up(delta=0.05)
                        current_vol = new_vol
                        is_muted = False
                        status_message = f"\033[1;32m🔊 Vol: {int(current_vol * 100)}%\033[0m"
                        status_msg_expires = time.time() + 2.0
                    except Exception:
                        pass

                elif cmd == "vol_down":
                    try:
                        new_vol = max(0.0, current_vol - 0.05)
                        if hasattr(cast, "set_volume"):
                            cast.set_volume(new_vol)
                        elif hasattr(cast, "volume_down"):
                            cast.volume_down(delta=0.05)
                        current_vol = new_vol
                        status_message = f"\033[1;32m🔉 Vol: {int(current_vol * 100)}%\033[0m"
                        status_msg_expires = time.time() + 2.0
                    except Exception:
                        pass

                elif cmd == "mute":
                    try:
                        is_muted = not is_muted
                        if hasattr(cast, "set_volume_muted"):
                            cast.set_volume_muted(is_muted)
                        else:
                            cast.socket_client.receiver_controller.set_volume_muted(is_muted)
                        status_message = "\033[1;31m🔇 Muted\033[0m" if is_muted else f"\033[1;32m🔊 Unmuted ({int(current_vol * 100)}%)\033[0m"
                        status_msg_expires = time.time() + 2.0
                    except Exception:
                        pass

                # 2. Check playback status
                if is_local:
                    if getattr(cast, "mpv_proc", None) and cast.mpv_proc.poll() is not None:
                        # mpv window closed or video playback completed
                        if duration > 0 and (last_known_position >= (duration * 0.88) or (duration - last_known_position) <= 45.0):
                            handle_exit("finished")
                            return
                        else:
                            handle_exit("quit")
                            return
                    try:
                        mc.update_status()
                    except Exception:
                        pass
                else:
                    is_conn = True
                    try:
                        is_conn = getattr(cast, "is_connected", True)
                    except Exception:
                        is_conn = False

                    if not is_conn:
                        disconnect_counter += 1
                        # Give internal connection 30 ticks (~7.5 seconds) to absorb Wi-Fi latency without aborting
                        if disconnect_counter >= 30:
                            raise ConnectionResetError("Chromecast connection dropped")
                    else:
                        disconnect_counter = 0

                status = None
                try:
                    status = mc.status
                except Exception:
                    pass

                if status:
                    pos = getattr(status, "adjusted_current_time", None) or getattr(status, "current_time", None)
                    if pos is not None and pos > 0:
                        last_known_position = pos

                    dur = getattr(status, "duration", None)
                    if dur and dur > 0:
                        duration = dur

                    if status.player_is_paused:
                        is_paused = True
                    elif status.player_is_playing:
                        is_paused = False

                    if getattr(cast, "status", None):
                        if getattr(cast.status, "volume_level", None) is not None:
                            current_vol = cast.status.volume_level
                        if getattr(cast.status, "volume_muted", None) is not None:
                            is_muted = cast.status.volume_muted

                    # Reset idle counter on active playback states
                    if status.player_is_playing or status.player_is_paused or status.player_state == "BUFFERING":
                        idle_counter = 0
                        if status.player_state == "BUFFERING":
                            status_message = "Buffering..."
                            status_msg_expires = time.time() + 1.2

                    elif status.player_state == "IDLE":
                        # Natural episode completion check
                        if status.idle_reason == "FINISHED":
                            if duration > 0:
                                if last_known_position >= (duration * 0.88) or (duration - last_known_position) <= 45.0:
                                    handle_exit("finished")
                                    return
                            else:
                                handle_exit("finished")
                                return

                        # Genuine interruption: only after persistent ERROR state (debounce 15 full seconds)
                        if time.time() - startup_time > 15.0:
                            if status.idle_reason in ["ERROR", "CANCELLED"]:
                                idle_counter += 1
                                if idle_counter >= 60:
                                    raise ConnectionResetError("Playback interrupted on TV")
                            else:
                                # None or INTERRUPTED: transient buffering or segment loading, do not interrupt
                                idle_counter = 0

                # Periodic save of resume position every 10 seconds
                if time.time() - last_save_time >= 10.0:
                    if last_known_position > 0:
                        save_resume_state(TITLE, last_known_position, duration, finished=False)
                    last_save_time = time.time()

                # 3. Render progress bar to terminal
                extra_msg = ""
                if time.time() < status_msg_expires and status_message:
                    extra_msg = f"  [{status_message}]"

                try:
                    cols = os.get_terminal_size().columns
                except Exception:
                    cols = 80
                bar_width = max(15, min(36, cols - 48))

                bar_str = render_bar(
                    last_known_position,
                    duration,
                    not is_paused,
                    current_vol,
                    is_muted,
                    width=bar_width
                )
                sys.stdout.write(f"\r\033[K{bar_str}{extra_msg}")
                sys.stdout.flush()

            except (KeyboardInterrupt, SystemExit):
                handle_exit("sigint")
                return
            except Exception:
                # Connection dropped: save progress
                if last_known_position > 0:
                    save_resume_state(TITLE, last_known_position, duration, finished=False)

                mins = int(last_known_position // 60)
                secs = int(last_known_position % 60)
                sys.stdout.write(f"\r\033[K\n\033[1;33m[!] Connection blip at {mins:02d}:{secs:02d}.\033[0m\n")
                sys.stdout.write("\033[1;36m[*] Re-syncing with TV... (Press Ctrl+C to stop)\033[0m\n")
                sys.stdout.flush()

                kbd.stop()

                # Disconnect old cast socket client cleanly to prevent high CPU / zombie threads
                try:
                    cast.disconnect()
                except Exception:
                    pass

                reconnected = False
                while not reconnected:
                    try:
                        time.sleep(1.5)
                        new_cast = None
                        # Try direct connection first for instant 0.3s re-attachment
                        if device_ip and device_ip != "127.0.0.1":
                            new_cast = connect_chromecast_direct(device_ip, chosen_device_name, timeout=2.0)
                        if not new_cast:
                            new_cast = discover_chromecast(silent=True, target_device=chosen_device_name)

                        if new_cast:
                            cast = new_cast
                            device_name = cast.name or chosen_device_name
                            device_ip = cast.cast_info.host if cast.cast_info else device_ip
                            local_ip = get_local_ip(device_ip)
                            mc = cast.media_controller

                            # Check if the TV is STILL actively playing our stream!
                            is_still_playing = False
                            try:
                                mc.update_status()
                                time.sleep(0.4)
                                st = mc.status
                                if st and st.player_state in ["PLAYING", "BUFFERING", "PAUSED"]:
                                    cur = getattr(st, "adjusted_current_time", None) or getattr(st, "current_time", None)
                                    if cur is not None and cur > 0:
                                        last_known_position = cur
                                    is_still_playing = True
                            except Exception:
                                is_still_playing = False

                            if is_still_playing:
                                # TV is already playing: DO NOT RESTART OR STOP! Just re-attach!
                                print(f"\033[1;32m[+] Re-synced with {device_name}! Playback is continuing on TV (no restart).\033[0m", flush=True)
                            else:
                                # TV was genuinely stopped/powered off: restart playback from last known position
                                m3u8_content, seg_urls, seg_start_times, total_manifest_duration = parse_and_rewrite_m3u8(
                                    raw_m3u8, local_ip, port, M3U8_URL
                                )
                                resume_pos = max(0.0, last_known_position - 2.0)
                                resume_seg_idx = find_segment_index(seg_start_times, resume_pos)
                                segment_buffer.seek(resume_seg_idx)

                                video_url = f"http://{local_ip}:{port}/playlist.m3u8"
                                sub_url = f"http://{local_ip}:{port}/subtitles.vtt" if has_subs else None

                                rmins = int(resume_pos // 60)
                                rsecs = int(resume_pos % 60)
                                print(f"\033[1;32m[+] Reconnected to {device_name}! Resuming from {rmins:02d}:{rsecs:02d}...\033[0m", flush=True)

                                mc = start_playback_on_cast(cast, video_url, sub_url, TITLE, current_time=resume_pos)
                                print(f"[+] Resumed playback on {device_name}!", flush=True)

                            reconnected = True
                            is_paused = False
                            startup_time = time.time()
                            idle_counter = 0
                            disconnect_counter = 0
                    except (KeyboardInterrupt, SystemExit):
                        handle_exit("sigint")
                        return
                    except Exception:
                        pass

                kbd.start()

    except (KeyboardInterrupt, SystemExit):
        handle_exit("sigint")
    finally:
        cleanup_terminal()

if __name__ == "__main__":
    main()
