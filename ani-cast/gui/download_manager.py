"""
Season downloader with smart completed-episode skipping.
Skips episodes marked finished or >=90% watched in resume_state.json,
and files already downloaded to ~/Videos/Anime/<Anime Title>/.
"""
import os
import sys
import re
import threading
import urllib.request
import yt_dlp
import gi

gi.require_version("GLib", "2.0")
from gi.repository import GLib

# Add parent lib to sys.path for anicast_engine
LIB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "lib"))
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

import anicast_engine

BASE_ANIME_DIR = os.path.expanduser("~/Videos/Anime")


class DownloadManager:
    def __init__(self):
        self.is_downloading = False
        self.cancel_requested = False
        self.current_title = ""
        self.current_ep_num = 0
        self.total_eps_in_season = 0
        self.eps_to_download = 0
        self.eps_completed = 0
        self.eps_skipped = 0

    def cancel(self):
        self.cancel_requested = True

    def start_season_download(
        self,
        anime_title: str,
        season_num: int,
        episodes_list: list,
        quality: str = "1080p",
        mode: str = "sub",
        on_progress=None,  # callback(dict_status)
        on_finished=None,  # callback(summary_dict)
    ):
        """
        Starts downloading entire season in a background thread.
        All callbacks dispatched safely via GLib.idle_add.
        """
        if self.is_downloading:
            return False

        self.is_downloading = True
        self.cancel_requested = False

        def _worker():
            try:
                clean_anime = re.sub(r'[/\\?%*:|"<>]', "_", anime_title.strip())
                season_str = f" Season {season_num}" if season_num > 1 else ""
                dest_dir_name = f"{clean_anime}{season_str}"
                dest_dir = os.path.join(BASE_ANIME_DIR, dest_dir_name)
                os.makedirs(dest_dir, exist_ok=True)

                resume_data = anicast_engine.load_resume_state()
                total_in_season = len(episodes_list)

                # 1. Pre-filter episodes to determine which need downloading
                queue = []
                skipped_eps = []

                for ep in episodes_list:
                    ep_num = ep["number"]
                    ep_id = ep["id"]
                    try:
                        ep_int = int(float(ep_num))
                    except Exception:
                        ep_int = ep_num

                    full_ep_title = (
                        f"{anime_title} Season {season_num} Episode {ep_num}"
                        if season_num > 1
                        else f"{anime_title} Episode {ep_num}"
                    )
                    out_filename = f"{clean_anime} - Episode {ep_int:02d}.mp4" if isinstance(ep_int, int) else f"{clean_anime} - Episode {ep_int}.mp4"
                    out_path = os.path.join(dest_dir, out_filename)

                    # Check 1: Watched & completed in resume_state.json
                    is_watched_done = False
                    for k, v in resume_data.items():
                        if k.strip().lower() == full_ep_title.strip().lower():
                            dur = float(v.get("duration", 0.0))
                            pos = float(v.get("position", 0.0))
                            if v.get("finished") or (dur > 0 and pos >= (dur * 0.90)):
                                is_watched_done = True
                                break

                    if is_watched_done:
                        skipped_eps.append({"number": ep_num, "reason": "Already completed"})
                        continue

                    # Check 2: Already on disk (> 5MB)
                    if os.path.exists(out_path) and os.path.getsize(out_path) > 5 * 1024 * 1024:
                        skipped_eps.append({"number": ep_num, "reason": "Already on disk"})
                        continue

                    queue.append({
                        "number": ep_num,
                        "int_num": ep_int,
                        "id": ep_id,
                        "title": full_ep_title,
                        "out_path": out_path,
                    })

                self.total_eps_in_season = total_in_season
                self.eps_to_download = len(queue)
                self.eps_skipped = len(skipped_eps)
                self.eps_completed = 0

                if on_progress:
                    GLib.idle_add(
                        on_progress,
                        {
                            "status": "starting",
                            "total": total_in_season,
                            "to_download": len(queue),
                            "skipped": len(skipped_eps),
                            "current_index": 0,
                            "percent": 0.0,
                            "speed": "",
                            "eta": "",
                            "message": f"Skipped {len(skipped_eps)} completed. Downloading {len(queue)} episodes.",
                        },
                    )

                if not queue:
                    if on_finished:
                        GLib.idle_add(
                            on_finished,
                            {
                                "status": "completed",
                                "downloaded": 0,
                                "skipped": len(skipped_eps),
                                "total": total_in_season,
                                "message": "All episodes already completed or downloaded!",
                            },
                        )
                    return

                # 2. Sequential download loop
                for q_idx, item in enumerate(queue, 1):
                    if self.cancel_requested:
                        break

                    ep_num = item["number"]
                    ep_id = item["id"]
                    out_path = item["out_path"]
                    ep_title = item["title"]

                    if on_progress:
                        overall_pct = (q_idx - 1) / len(queue)
                        GLib.idle_add(
                            on_progress,
                            {
                                "status": "resolving",
                                "total": total_in_season,
                                "to_download": len(queue),
                                "skipped": len(skipped_eps),
                                "current_index": q_idx,
                                "current_ep": ep_num,
                                "percent": overall_pct,
                                "speed": "",
                                "eta": "",
                                "message": f"Resolving Episode {ep_num} ({q_idx}/{len(queue)})...",
                            },
                        )

                    stream_info = anicast_engine.resolve_stream(
                        ep_id, mode=mode, preferred_quality=quality
                    )
                    if not stream_info:
                        continue

                    if self.cancel_requested:
                        break

                    vid_url = stream_info["video_url"]
                    referer = stream_info["referer"]
                    sub_url = stream_info.get("sub_url", "")

                    # Subtitles
                    if sub_url:
                        sub_path = out_path.rsplit(".", 1)[0] + ".vtt"
                        try:
                            s_req = urllib.request.Request(
                                sub_url,
                                headers={"Referer": referer, "User-Agent": "Mozilla/5.0"},
                            )
                            with urllib.request.urlopen(s_req, timeout=8) as sresp:
                                with open(sub_path, "wb") as sf:
                                    sf.write(sresp.read())
                        except Exception:
                            pass

                    # yt-dlp progress hook
                    def _ytdl_hook(d):
                        if self.cancel_requested:
                            raise Exception("Download cancelled by user")
                        if d["status"] == "downloading" and on_progress:
                            downloaded_b = d.get("downloaded_bytes", 0)
                            total_b = d.get("total_bytes") or d.get("total_bytes_estimate", 1)
                            ep_pct = min(1.0, max(0.0, downloaded_b / total_b)) if total_b else 0.0
                            overall_pct = ((q_idx - 1) + ep_pct) / len(queue)
                            speed_str = d.get("_speed_str", "").strip()
                            eta_str = d.get("_eta_str", "").strip()
                            pct_str = d.get("_percent_str", f"{int(ep_pct * 100)}%").strip()

                            GLib.idle_add(
                                on_progress,
                                {
                                    "status": "downloading",
                                    "total": total_in_season,
                                    "to_download": len(queue),
                                    "skipped": len(skipped_eps),
                                    "current_index": q_idx,
                                    "current_ep": ep_num,
                                    "percent": overall_pct,
                                    "ep_percent": ep_pct,
                                    "speed": speed_str,
                                    "eta": eta_str,
                                    "message": f"Downloading Ep {ep_num} ({q_idx}/{len(queue)}): {pct_str} at {speed_str} (ETA {eta_str})",
                                },
                            )

                    ydl_opts = {
                        "quiet": True,
                        "no_warnings": True,
                        "outtmpl": out_path,
                        "http_headers": {
                            "Referer": referer,
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                        },
                        "concurrent_fragment_downloads": 16,
                        "fragment_retries": 10,
                        "progress_hooks": [_ytdl_hook],
                    }

                    try:
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            ydl.download([vid_url])
                        self.eps_completed += 1
                    except Exception as e:
                        if self.cancel_requested:
                            # Clean up partial
                            part_file = f"{out_path}.part"
                            if os.path.exists(part_file):
                                try:
                                    os.remove(part_file)
                                except Exception:
                                    pass
                            break

                final_status = "cancelled" if self.cancel_requested else "completed"
                if on_finished:
                    GLib.idle_add(
                        on_finished,
                        {
                            "status": final_status,
                            "downloaded": self.eps_completed,
                            "skipped": len(skipped_eps),
                            "total": total_in_season,
                            "message": f"Finished: {self.eps_completed} downloaded, {len(skipped_eps)} skipped.",
                        },
                    )

            finally:
                self.is_downloading = False

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        return True
