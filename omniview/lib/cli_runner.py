#!/usr/bin/env python3
"""
OmniView Unified CLI Runner
Handles interactive searches, symmetrical table presentation, episode selection,
and clean, clutter-free MPV and Chromecast playback.
"""
import os
import sys
import json
import time
import signal
import subprocess
from typing import List, Dict, Optional, Any

LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

import cli_view as ui
import anicast_engine
import movies_engine

STATE_DIR = os.path.expanduser("~/.local/state/omniview")
RESUME_FILE = os.path.join(STATE_DIR, "resume_state.json")
RUNTIME_DIR = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
SESSION_FILE = os.path.join(RUNTIME_DIR, "omniview_current_session.json")
ACTION_FILE = os.path.join(RUNTIME_DIR, "omniview_action")
BASE_DIR = os.path.abspath(os.path.join(LIB_DIR, ".."))


def cleanup_session():
    for f in [ACTION_FILE, os.path.join(RUNTIME_DIR, "omniview_next_season_pending"), SESSION_FILE]:
        try:
            if os.path.exists(f):
                os.remove(f)
        except Exception:
            pass


def get_resume_position(title: str) -> float:
    data = anicast_engine.load_resume_state()
    for k, v in data.items():
        if k.strip().lower() == title.strip().lower():
            if not v.get("finished", False):
                pos = float(v.get("position", 0.0))
                dur = float(v.get("duration", 0.0))
                if dur <= 0 or pos < (dur - 25.0):
                    return pos
    return 0.0


def play_local_mpv(stream_url: str, title: str, referer: str = "", sub_url: str = "", start_time: float = 0.0) -> int:
    """
    Launches MPV cleanly with suppressed terminal noise and active Lua resume tracking.
    """
    ui.print_status_box("PLAYING", f"{title} (MPV)", ui.GREEN)

    cmd = [
        "mpv",
        f"--force-media-title={title}",
        f"--script={BASE_DIR}/lib/ani_cast_mpv_resume.lua",
        "--keep-open=no",
        "--msg-level=all=error",  # Suppress internal player debug spew
    ]
    if referer:
        cmd.append(f"--referrer={referer}")
    cmd.append("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    if sub_url:
        cmd.append(f"--sub-file={sub_url}")
    if start_time and start_time > 0:
        cmd.append(f"--start={start_time}")

    cmd.append(stream_url)

    try:
        proc = subprocess.run(cmd)
        return proc.returncode
    except KeyboardInterrupt:
        return 130


def play_chromecast(stream_url: str, title: str, device_name: str = "TV", referer: str = "", sub_url: str = "", start_time: float = 0.0) -> int:
    """
    Streams media to Chromecast via hls_streamer.py.
    """
    ui.print_status_box("CASTING", f"{title} -> {device_name}", ui.SAPPHIRE)

    env = os.environ.copy()
    env["OMNIVIEW_DEVICE"] = device_name
    env["ANI_CAST_DEVICE"] = device_name
    if start_time and start_time > 0:
        env["OMNIVIEW_START_TIME"] = str(round(start_time, 1))
        env["ANI_CAST_START_TIME"] = str(round(start_time, 1))

    hls_script = os.path.join(LIB_DIR, "hls_streamer.py")
    cmd = [
        sys.executable,
        hls_script,
        referer or "https://vidsrc.su",
        stream_url,
        sub_url or "",
        title,
        str(round(start_time, 1)) if start_time else "0",
    ]

    try:
        proc = subprocess.run(cmd, env=env)
        return proc.returncode
    except KeyboardInterrupt:
        return 130


def run_interactive_selection(
    query: str,
    target_mode: str = "local",
    device_name: str = "This Device",
    force_type: Optional[str] = None,
    quality: str = "1080p",
    mode: str = "sub",
    season_opt: Optional[int] = None,
    episode_opt: Optional[int] = None,
):
    ui.print_banner()

    if not query:
        print(f" {ui.BOLD}{ui.SAPPHIRE}Search OmniView (Anime, Movies, TV Shows):{ui.RESET} ", end="", flush=True)
        try:
            query = input().strip()
        except (KeyboardInterrupt, EOFError):
            print()
            sys.exit(0)

    if not query:
        print(f" {ui.RED}[!] No search query entered. Exiting.{ui.RESET}")
        sys.exit(1)

    ui.print_status_box("SEARCH", f"Querying media repositories for '{query}'...", ui.MAUVE)

    items: List[Dict[str, Any]] = []

    # 1. Fetch Anime results (unless forced movie/show)
    if force_type in [None, "anime"]:
        try:
            anime_res = anicast_engine.search_anime(query)
            for a in anime_res[:6]:
                items.append({
                    "title": a["title"],
                    "slug": a["slug"],
                    "id": a["id"],
                    "type": "anime",
                    "poster": a.get("poster"),
                })
        except Exception:
            pass

    # 2. Fetch Movies & TV Shows results (unless forced anime)
    if force_type in [None, "movie", "tv", "show"]:
        try:
            m_res = movies_engine.search_movies_and_shows(query)
            for m in m_res[:6]:
                items.append({
                    "title": m["title"],
                    "id": m["id"],
                    "type": m["type"],
                    "year": m.get("year", "N/A"),
                    "poster": m.get("poster"),
                    "cast": m.get("cast", ""),
                })
        except Exception:
            pass

    if not items:
        print(f"\n {ui.RED}[!] No media found matching '{query}'. Try another search.{ui.RESET}\n")
        sys.exit(1)

    print()
    ui.render_search_results(items)
    target_label = "Local Screen (MPV)" if target_mode == "local" else f"Chromecast ({device_name})"
    ui.render_action_bar(len(items), target_label)

    # User Selection Prompt
    selected_idx = 1
    action = None
    while True:
        try:
            prompt_str = f" {ui.BOLD}{ui.MAUVE}OmniView ❯{ui.RESET} "
            choice = input(prompt_str).strip()
        except (KeyboardInterrupt, EOFError):
            print()
            sys.exit(0)

        if choice.lower() in ["q", "quit", "exit"]:
            print(f" {ui.SUBTEXT}Exiting.{ui.RESET}")
            sys.exit(0)
        elif choice.lower() in ["l", "local"]:
            target_mode = "local"
            ui.print_status_box("MODE", "Switched playback target to Local MPV", ui.GREEN)
            continue
        elif choice.lower() in ["c", "cast"]:
            target_mode = "cast"
            ui.print_status_box("MODE", f"Switched playback target to Cast TV ({device_name})", ui.SAPPHIRE)
            continue
        elif choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(items):
                selected_idx = idx
                break
            else:
                print(f" {ui.RED}[!] Please select between 1 and {len(items)}{ui.RESET}")
        elif choice == "":
            selected_idx = 1
            break
        else:
            print(f" {ui.RED}[!] Invalid choice. Enter [1-{len(items)}], [l], [c], or [q]{ui.RESET}")

    selected_item = items[selected_idx - 1]
    media_type = selected_item["type"]
    title = selected_item["title"]

    ui.print_status_box("SELECTED", f"{title} ({media_type.upper()})", ui.GREEN)

    # Handle Playback by Media Type
    if media_type == "movie":
        stream_info = movies_engine.resolve_movie_stream(selected_item["id"], title)
        start_ts = get_resume_position(title)
        if start_ts > 5.0:
            ui.print_status_box("RESUME", f"Resuming from timestamp {unicast_format_time(start_ts)}", ui.YELLOW)

        if target_mode == "local":
            play_local_mpv(
                stream_info["video_url"],
                title,
                referer=stream_info["referer"],
                sub_url=stream_info.get("sub_url", ""),
                start_time=start_ts,
            )
        else:
            play_chromecast(
                stream_info["master_url"],
                title,
                device_name=device_name,
                referer=stream_info["referer"],
                sub_url=stream_info.get("sub_url", ""),
                start_time=start_ts,
            )

    elif media_type == "tv":
        ui.print_status_box("SEASONS", f"Loading episodes for {title}...", ui.SAPPHIRE)
        seasons_dict = movies_engine.get_tv_seasons_and_episodes(selected_item["id"], title)
        available_seasons = sorted(seasons_dict.keys())
        target_s = season_opt if (season_opt and season_opt in seasons_dict) else available_seasons[0]
        episodes = seasons_dict[target_s]

        # Episode selection
        ep_num = episode_opt
        if not ep_num or ep_num > len(episodes):
            print(f"\n {ui.BOLD}{ui.SAPPHIRE}Episodes in Season {target_s} ({len(episodes)} total):{ui.RESET}")
            ep_headers = [("EP", 4, "center"), ("TITLE", 40, "left"), ("AIRDATE", 12, "center")]
            ep_rows = []
            for ep in episodes[:16]:
                ep_rows.append([
                    (str(ep["number"]), ui.BOLD + ui.TEXT),
                    (ep["title"], ui.TEXT),
                    (ep.get("airdate") or "N/A", ui.SUBTEXT),
                ])
            ui.render_table(ep_headers, ep_rows)

            try:
                print(f" {ui.BOLD}Select Episode [1-{len(episodes)}] (default 1):{ui.RESET} ", end="", flush=True)
                ep_in = input().strip()
                ep_num = int(ep_in) if ep_in.isdigit() and 1 <= int(ep_in) <= len(episodes) else 1
            except (KeyboardInterrupt, EOFError):
                print()
                sys.exit(0)

        full_ep_title = f"{title} S{target_s:02d}E{ep_num:02d}"
        stream_info = movies_engine.resolve_tv_stream(selected_item["id"], target_s, ep_num, title)
        start_ts = get_resume_position(full_ep_title)
        if start_ts > 5.0:
            ui.print_status_box("RESUME", f"Resuming from timestamp {unicast_format_time(start_ts)}", ui.YELLOW)

        if target_mode == "local":
            play_local_mpv(
                stream_info["video_url"],
                full_ep_title,
                referer=stream_info["referer"],
                sub_url=stream_info.get("sub_url", ""),
                start_time=start_ts,
            )
        else:
            play_chromecast(
                stream_info["master_url"],
                full_ep_title,
                device_name=device_name,
                referer=stream_info["referer"],
                sub_url=stream_info.get("sub_url", ""),
                start_time=start_ts,
            )

    else:
        # Anime
        slug = selected_item["slug"]
        ui.print_status_box("EPISODES", f"Loading episodes for {title}...", ui.MAUVE)
        episodes = anicast_engine.get_episodes(slug)
        if not episodes:
            print(f" {ui.RED}[!] Could not retrieve anime episodes.{ui.RESET}")
            sys.exit(1)

        ep_num = episode_opt or 1
        if not episode_opt:
            print(f"\n {ui.BOLD}{ui.MAUVE}Anime Episodes ({len(episodes)} total):{ui.RESET}")
            ep_headers = [("EP", 4, "center"), ("EPISODE NAME", 40, "left"), ("ID", 12, "center")]
            ep_rows = []
            for ep in episodes[:16]:
                ep_rows.append([
                    (str(ep["number"]), ui.BOLD + ui.TEXT),
                    (ep.get("title") or f"Episode {ep['number']}", ui.TEXT),
                    (str(ep["id"]), ui.SUBTEXT),
                ])
            ui.render_table(ep_headers, ep_rows)

            try:
                print(f" {ui.BOLD}Select Episode [1-{len(episodes)}] (default 1):{ui.RESET} ", end="", flush=True)
                ep_in = input().strip()
                ep_num = int(ep_in) if ep_in.isdigit() and 1 <= int(ep_in) <= len(episodes) else 1
            except (KeyboardInterrupt, EOFError):
                print()
                sys.exit(0)

        ep_obj = next((e for e in episodes if int(float(e["number"])) == ep_num), episodes[0])
        full_ep_title = f"{title} Episode {ep_num}"
        ui.print_status_box("RESOLVING", f"Resolving stream ({mode}, {quality})...", ui.MAUVE)
        stream_info = anicast_engine.resolve_stream(ep_obj["id"], mode=mode, preferred_quality=quality)
        if not stream_info:
            print(f" {ui.RED}[!] Could not resolve stream.{ui.RESET}")
            sys.exit(1)

        start_ts = get_resume_position(full_ep_title)
        if start_ts > 5.0:
            ui.print_status_box("RESUME", f"Resuming from timestamp {unicast_format_time(start_ts)}", ui.YELLOW)

        if target_mode == "local":
            play_local_mpv(
                stream_info["video_url"],
                full_ep_title,
                referer=stream_info["referer"],
                sub_url=stream_info.get("sub_url", ""),
                start_time=start_ts,
            )
        else:
            play_chromecast(
                stream_info.get("master_url") or stream_info["video_url"],
                full_ep_title,
                device_name=device_name,
                referer=stream_info["referer"],
                sub_url=stream_info.get("sub_url", ""),
                start_time=start_ts,
            )


def unicast_format_time(seconds: float) -> str:
    s = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def handle_continue(query: Optional[str] = None):
    ui.print_banner()
    target = anicast_engine.resolve_continue_target(query)
    if not target:
        print(f" {ui.RED}[!] No matching watch history found to continue.{ui.RESET}")
        sys.exit(1)

    title = target["anime_base"]
    s = target["season"]
    e = target["episode"]
    ts = target["timestamp"]
    time_str = target["time_str"]

    if target["was_completed"]:
        ui.print_status_box("CONTINUE", f"Advancing to Next Episode: {title} S{s}E{e}", ui.GREEN)
    else:
        ui.print_status_box("CONTINUE", f"Resuming {title} S{s}E{e} from {time_str}", ui.YELLOW)

    run_interactive_selection(title, season_opt=s, episode_opt=e)


if __name__ == "__main__":
    query_args = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""
    run_interactive_selection(query_args)
