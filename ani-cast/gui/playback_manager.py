"""
Playback coordinator for AniCast.
Handles streaming to TV (via hls_streamer.py) and local screen (via MPV with IPC socket),
saving resume state, and auto-advancing across episodes and seasons.
"""
import os
import sys
import time
import socket
import json
import signal
import subprocess
import threading
import gi

gi.require_version("GLib", "2.0")
from gi.repository import GLib

# Add parent lib to sys.path for anicast_engine
LIB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "lib"))
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

import anicast_engine

RESUME_FILE = os.path.expanduser("~/.local/state/ani-cast/resume_state.json")
LOCAL_HLS = os.path.abspath(os.path.join(LIB_DIR, "hls_streamer.py"))
HLS_STREAMER_PY = LOCAL_HLS if os.path.exists(LOCAL_HLS) else os.path.expanduser("~/Videos/Anime/hls_streamer.py")


def save_resume_state(title: str, position: float, duration: float = 0.0, finished: bool = False):
    if not title:
        return
    try:
        os.makedirs(os.path.dirname(RESUME_FILE), exist_ok=True)
        data = anicast_engine.load_resume_state()
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


def get_resume_position(title: str) -> float:
    data = anicast_engine.load_resume_state()
    for k, v in data.items():
        if k.strip().lower() == title.strip().lower():
            if not v.get("finished", False):
                pos = float(v.get("position", 0.0))
                dur = float(v.get("duration", 0.0))
                if dur > 0 and (pos >= (dur - 25.0) or pos >= (dur * 0.92)):
                    return 0.0
                return pos
            return 0.0
    return 0.0


class PlaybackManager:
    def __init__(self, on_status_change=None, on_auto_advance=None):
        self.on_status_change = on_status_change
        self.on_auto_advance = on_auto_advance

        self.current_process = None
        self.current_proc_type = None  # "mpv" or "cast"
        self.current_title = None
        self.current_anime = None
        self.current_season = 1
        self.current_ep = 1
        self.current_episodes_list = []
        self.current_device = None
        self.current_mode = "sub"
        self.current_quality = "1080p"

        self._stop_requested = False
        self._ipc_thread = None

    def is_playing(self) -> bool:
        return self.current_process is not None and self.current_process.poll() is None

    def stop_playback(self):
        self._stop_requested = True
        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.terminate()
                self.current_process.wait(timeout=1.5)
            except Exception:
                try:
                    self.current_process.kill()
                except Exception:
                    pass
        self.current_process = None
        self.current_proc_type = None
        if self.on_status_change:
            GLib.idle_add(self.on_status_change, "stopped", None)

    def play_episode(
        self,
        anime_title: str,
        season_num: int,
        episode_num: int,
        ep_id: str,
        episodes_list: list,
        target_device: dict = None,
        mode: str = "sub",
        quality: str = "1080p",
        explicit_start_time: float = None,
    ):
        """
        Resolves stream and starts playback on target_device (defaults to local screen).
        Runs in background thread so UI doesn't hitch.
        """
        self.stop_playback()
        self._stop_requested = False

        if not target_device:
            target_device = {
                "name": "This Device (Local Screen / MPV)",
                "id": "local",
                "ip": "127.0.0.1",
                "model": "Local Screen",
                "is_local": True,
            }

        base_anime, _, _ = anicast_engine.parse_anime_title(anime_title)
        self.current_anime = base_anime
        self.current_season = season_num
        self.current_ep = episode_num
        self.current_episodes_list = episodes_list
        self.current_device = target_device
        self.current_mode = mode
        self.current_quality = quality

        full_title = (
            f"{base_anime} Season {season_num} Episode {episode_num}"
            if season_num > 1
            else f"{base_anime} Episode {episode_num}"
        )
        self.current_title = full_title

        if self.on_status_change:
            GLib.idle_add(self.on_status_change, "loading", full_title)

        def _worker():
            try:
                # 1. Resolve stream
                stream_info = anicast_engine.resolve_stream(
                    ep_id, mode=mode, preferred_quality=quality
                )
                if not stream_info:
                    if self.on_status_change:
                        GLib.idle_add(self.on_status_change, "error", f"Could not resolve stream for {full_title}")
                    return

                if self._stop_requested:
                    return

                vid_url = stream_info["video_url"]
                master_url = stream_info.get("master_url") or vid_url
                referer = stream_info["referer"]
                sub_url = stream_info.get("sub_url", "")

                # 2. Determine start time
                start_time = explicit_start_time
                if start_time is None:
                    start_time = get_resume_position(full_title)
                    if start_time > 5.0:
                        start_time = max(0.0, start_time - 2.0)
                    else:
                        start_time = 0.0

                is_local = target_device.get("is_local", True)

                if is_local:
                    self._play_local_mpv(vid_url, referer, sub_url, full_title, start_time)
                else:
                    self._play_chromecast(master_url, referer, sub_url, full_title, start_time, target_device)

            except Exception as e:
                if self.on_status_change:
                    GLib.idle_add(self.on_status_change, "error", str(e))

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def _play_local_mpv(self, video_url, referer, sub_url, title, start_time):
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
        sock_path = os.path.join(runtime_dir, f"anicast_mpv_{os.getpid()}_{int(time.time())}.sock")
        if os.path.exists(sock_path):
            try:
                os.remove(sock_path)
            except Exception:
                pass

        cmd = [
            "mpv",
            f"--input-ipc-server={sock_path}",
            f"--force-media-title={title}",
            f"--referrer={referer}",
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "--keep-open=no",
        ]
        if sub_url:
            cmd.append(f"--sub-file={sub_url}")
        if start_time and start_time > 0:
            cmd.append(f"--start={start_time}")
        cmd.append(video_url)

        proc = subprocess.Popen(cmd)
        self.current_process = proc
        self.current_proc_type = "mpv"

        if self.on_status_change:
            GLib.idle_add(self.on_status_change, "playing", title)

        # Monitor MPV playback via IPC socket in background
        def _monitor_ipc():
            last_pos = start_time or 0.0
            last_dur = 0.0
            last_saved_pos = last_pos
            last_save_time = time.time()
            eof_reached = False
            client = None
            sock_file = None

            # Connect to socket
            for _ in range(25):
                if os.path.exists(sock_path):
                    try:
                        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                        client.connect(sock_path)
                        client.settimeout(1.0)
                        sock_file = client.makefile("r", encoding="utf-8")
                        break
                    except Exception:
                        if client:
                            try:
                                client.close()
                            except Exception:
                                pass
                        client = None
                        sock_file = None
                time.sleep(0.15)

            while proc.poll() is None and not self._stop_requested:
                if client and sock_file:
                    try:
                        client.sendall(json.dumps({"command": ["get_property", "time-pos"], "request_id": 1}).encode("utf-8") + b"\n")
                        client.sendall(json.dumps({"command": ["get_property", "duration"], "request_id": 2}).encode("utf-8") + b"\n")

                        for _ in range(10):
                            try:
                                line = sock_file.readline()
                            except (socket.timeout, TimeoutError):
                                break
                            if not line:
                                break
                            try:
                                msg = json.loads(line)
                            except Exception:
                                continue

                            if msg.get("event") == "end-file":
                                if msg.get("reason") == "eof":
                                    eof_reached = True

                            req_id = msg.get("request_id")
                            if req_id == 1 and msg.get("data") is not None:
                                try:
                                    last_pos = float(msg["data"])
                                except (ValueError, TypeError):
                                    pass
                            elif req_id == 2:
                                if msg.get("data") is not None:
                                    try:
                                        last_dur = float(msg["data"])
                                    except (ValueError, TypeError):
                                        pass
                                break
                    except Exception:
                        pass

                    now = time.time()
                    if last_pos > 0 and (abs(last_pos - last_saved_pos) >= 3.0 or (now - last_save_time) >= 5.0):
                        save_resume_state(title, last_pos, last_dur, finished=False)
                        last_saved_pos = last_pos
                        last_save_time = now

                time.sleep(1.5)

            # Drain any final events from MPV
            if client and sock_file:
                try:
                    client.settimeout(0.3)
                    for _ in range(10):
                        line = sock_file.readline()
                        if not line:
                            break
                        msg = json.loads(line)
                        if msg.get("event") == "end-file" and msg.get("reason") == "eof":
                            eof_reached = True
                except Exception:
                    pass

            if sock_file:
                try:
                    sock_file.close()
                except Exception:
                    pass
            if client:
                try:
                    client.close()
                except Exception:
                    pass
            if os.path.exists(sock_path):
                try:
                    os.remove(sock_path)
                except Exception:
                    pass

            finished = False
            if eof_reached:
                finished = True
            elif last_dur > 0 and (last_pos >= (last_dur - 25.0) or last_pos >= (last_dur * 0.92)):
                finished = True

            if finished:
                save_resume_state(title, 0.0, last_dur, finished=True)
            elif last_pos > 0:
                save_resume_state(title, last_pos, last_dur, finished=False)

            if self.on_status_change:
                GLib.idle_add(self.on_status_change, "stopped", None)

            if finished and not self._stop_requested:
                self._handle_episode_finished()

        self._ipc_thread = threading.Thread(target=_monitor_ipc, daemon=True)
        self._ipc_thread.start()

    def _play_chromecast(self, master_url, referer, sub_url, title, start_time, target_device):
        env = os.environ.copy()
        dev_name = target_device.get("name", "TV")
        env["ANI_CAST_DEVICE"] = dev_name
        if start_time and start_time > 0:
            env["ANI_CAST_START_TIME"] = str(round(start_time, 1))

        # Download subtitles file locally if present
        cache_dir = os.path.expanduser("~/.cache/ani-cast")
        os.makedirs(cache_dir, exist_ok=True)
        sub_file = os.path.join(cache_dir, "subtitles.vtt")
        if sub_url:
            try:
                import urllib.request
                req = urllib.request.Request(sub_url, headers={"Referer": referer, "User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5) as r, open(sub_file, "wb") as f:
                    f.write(r.read())
            except Exception:
                sub_file = ""
        else:
            sub_file = ""

        cmd = [
            sys.executable,
            HLS_STREAMER_PY,
            referer,
            master_url,
            sub_file,
            title,
            str(round(start_time, 1)) if start_time else "0",
        ]

        proc = subprocess.Popen(cmd, env=env)
        self.current_process = proc
        self.current_proc_type = "cast"

        if self.on_status_change:
            GLib.idle_add(self.on_status_change, "playing", title)

        def _monitor_cast():
            ret = proc.wait()
            if self.on_status_change:
                GLib.idle_add(self.on_status_change, "stopped", None)

            # hls_streamer exits with 0 on normal finish
            if ret == 0 and not self._stop_requested:
                self._handle_episode_finished()

        threading.Thread(target=_monitor_cast, daemon=True).start()

    def _handle_episode_finished(self):
        """
        Auto-advance across episodes and seasons!
        1. If episode N+1 exists in current season: advance to N+1!
        2. If season finale: discover Season S+1 and advance to Season S+1 Episode 1!
        """
        if self._stop_requested:
            return

        next_ep_num = self.current_ep + 1
        found_next_in_season = None

        if self.current_episodes_list:
            for ep in self.current_episodes_list:
                try:
                    if int(float(ep["number"])) == next_ep_num:
                        found_next_in_season = ep
                        break
                except Exception:
                    pass

        if found_next_in_season:
            # Advance to next episode in current season
            if self.on_auto_advance:
                GLib.idle_add(
                    self.on_auto_advance,
                    self.current_anime,
                    self.current_season,
                    next_ep_num,
                    found_next_in_season["id"],
                )
            self.play_episode(
                self.current_anime,
                self.current_season,
                next_ep_num,
                found_next_in_season["id"],
                self.current_episodes_list,
                self.current_device,
                mode=self.current_mode,
                quality=self.current_quality,
                explicit_start_time=0.0,
            )
            return

        # Current season completed! Check for Season + 1
        def _check_next_season():
            nxt = anicast_engine.find_next_season(self.current_anime, self.current_season)
            if nxt and not self._stop_requested:
                nxt_slug = nxt["slug"]
                nxt_season_num = nxt["season"]
                nxt_episodes = anicast_engine.get_episodes(nxt_slug)
                if nxt_episodes:
                    first_ep = nxt_episodes[0]
                    first_ep_num = 1
                    try:
                        first_ep_num = int(float(first_ep["number"]))
                    except Exception:
                        pass

                    if self.on_auto_advance:
                        GLib.idle_add(
                            self.on_auto_advance,
                            self.current_anime,
                            nxt_season_num,
                            first_ep_num,
                            first_ep["id"],
                        )
                    self.play_episode(
                        self.current_anime,
                        nxt_season_num,
                        first_ep_num,
                        first_ep["id"],
                        nxt_episodes,
                        self.current_device,
                        mode=self.current_mode,
                        quality=self.current_quality,
                        explicit_start_time=0.0,
                    )

        threading.Thread(target=_check_next_season, daemon=True).start()
