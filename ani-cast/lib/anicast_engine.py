#!/usr/bin/env python3
"""
ani-cast core engine
Provides resume state resolution, season advance detection, HiAnime stream extraction,
and smart season downloader with completed-episode skipping.
"""
import sys
import os
import re
import json
import time
import base64
import urllib.parse
import urllib.request
import subprocess

RESUME_FILE = os.path.expanduser("~/.local/state/ani-cast/resume_state.json")
SESSION_FILE = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "ani_cast_current_session.json")
ACTION_FILE = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "ani_cast_action")

BASE_URL = "https://hianime.at"
SEARCH_URL = f"{BASE_URL}/search?keyword="
EPISODES_URL = f"{BASE_URL}/api/theme/episode/list/"
SERVERS_URL = f"{BASE_URL}/api/theme/episode/servers?episodeId="
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
}
XOR_KEY = b"otaku-embed-v1"

def format_time(seconds):
    if not seconds or seconds < 0:
        return "00:00"
    s = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

def load_resume_state():
    if os.path.exists(RESUME_FILE):
        try:
            with open(RESUME_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def parse_anime_title(title):
    """
    Parses 'Blue Lock Season 2 Episode 7' -> ('Blue Lock', 2, 7)
    'Blue Lock Season 2' -> ('Blue Lock', 2, 1)
    'The Irregular at Magic High School Episode 15' -> ('The Irregular at Magic High School', 1, 15)
    """
    m = re.search(r'^(.*?)(?:\s+Season\s+(\d+))?\s+Episode\s+(\d+)', title, re.IGNORECASE)
    if m:
        anime = m.group(1).strip()
        season = int(m.group(2)) if m.group(2) else 1
        ep = int(m.group(3))
        return anime, season, ep
    m2 = re.search(r'^(.*?)\s+Episode\s+(\d+)', title, re.IGNORECASE)
    if m2:
        return m2.group(1).strip(), 1, int(m2.group(2))
    m3 = re.search(r'^(.*?)\s+Season\s+(\d+)', title, re.IGNORECASE)
    if m3:
        return m3.group(1).strip(), int(m3.group(2)), 1
    return title.strip(), 1, 1

def deobfuscate_blob(blob):
    try:
        data = base64.b64decode(blob)
        out = bytearray(len(data))
        for i, b in enumerate(data):
            out[i] = b ^ XOR_KEY[i % len(XOR_KEY)]
        return out.decode("utf-8", errors="ignore")
    except Exception:
        return ""

def http_get(url, headers=None, is_json=False):
    req_headers = dict(DEFAULT_HEADERS)
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = resp.read()
            if is_json:
                return json.loads(data.decode("utf-8"))
            return data.decode("utf-8", errors="ignore")
    except Exception:
        return None

def search_anime(query):
    if not query or not query.strip():
        return []
    url = SEARCH_URL + urllib.parse.quote(query.strip())
    html = http_get(url)
    if not html:
        return []
    if 'id="main-sidebar"' in html:
        html = html.split('id="main-sidebar"')[0]

    poster_pattern = re.compile(
        r'<div class="film-poster">.*?<img\s+[^>]*src="([^"]+)"[^>]*class="film-poster-img".*?<h3 class="film-name">\s*<a href="[^"]*/([^"/]*)"[^>]*title="([^"]*)"',
        re.DOTALL
    )
    matches = poster_pattern.findall(html)
    results = []
    seen = set()
    if matches:
        for poster, slug, title in matches:
            clean_title = (
                title.replace("&#039;", "'")
                .replace("&quot;", '"')
                .replace("&amp;", "&")
                .strip()
            )
            anime_id = slug.split("-")[-1] if "-" in slug else slug
            if slug not in seen:
                seen.add(slug)
                results.append({
                    "title": clean_title,
                    "slug": slug,
                    "id": anime_id,
                    "poster": poster
                })
        return results

    pattern = re.compile(
        r'<h3 class="film-name">\s*<a href="[^"]*/([^"/]*)"[^>]*title="([^"]*)"',
        re.DOTALL
    )
    for slug, title in pattern.findall(html):
        clean_title = (
            title.replace("&#039;", "'")
            .replace("&quot;", '"')
            .replace("&amp;", "&")
            .strip()
        )
        anime_id = slug.split("-")[-1] if "-" in slug else slug
        if slug not in seen:
            seen.add(slug)
            results.append({
                "title": clean_title,
                "slug": slug,
                "id": anime_id,
                "poster": None
            })
    return results

def get_episodes(anime_slug_or_id):
    anime_id = anime_slug_or_id.split("-")[-1] if "-" in str(anime_slug_or_id) else str(anime_slug_or_id)
    url = f"{EPISODES_URL}{anime_id}"
    data = http_get(url, headers={"X-Requested-With": "XMLHttpRequest"}, is_json=True)
    if not data or "html" not in data:
        return []
    html = data["html"]
    pattern = re.compile(r'data-number="([^"]*)".*?data-id="([0-9]+)"', re.DOTALL)
    episodes = []
    seen = set()
    for ep_num, ep_id in pattern.findall(html):
        if ep_num not in seen:
            seen.add(ep_num)
            episodes.append({
                "number": ep_num,
                "id": ep_id,
                "title": f"Episode {ep_num}"
            })
    return episodes

def get_related_seasons(anime_slug):
    url = f"{BASE_URL}/watch/{anime_slug}"
    html = http_get(url)
    if not html:
        return []
    matches = re.findall(r'<a[^>]*href=\"https://hianime\.at/watch/([^\"]+)\"[^>]*class=\"[^\"]*os-item[^\"]*\"[^>]*title=\"([^\"]+)\"', html)
    seasons = []
    seen = set()
    for s_slug, s_title in matches:
        if s_slug not in seen:
            seen.add(s_slug)
            clean_title = s_title.replace('&#039;', "'").replace('&quot;', '"').replace('&amp;', '&').strip()
            _, s_num, _ = parse_anime_title(clean_title)
            seasons.append({'title': clean_title, 'slug': s_slug, 'season': s_num})
    seasons.sort(key=lambda x: x['season'])
    return seasons

def resolve_stream(episode_id, mode="sub", preferred_quality="1080p"):
    url = f"{SERVERS_URL}{episode_id}"
    data = http_get(url, headers={"X-Requested-With": "XMLHttpRequest"}, is_json=True)
    if not data or "html" not in data:
        return None
    html = data["html"]

    # Match requested mode and preferred server (ZokoAnime or first available)
    pattern = re.compile(r'data-type="' + mode + r'"[^>]*data-server-name="ZokoAnime"[^>]*data-hash="([^"]*)"')
    m = pattern.search(html)
    if not m:
        m = re.search(r'data-type="' + mode + r'"[^>]*data-hash="([^"]*)"', html)
    if not m:
        m = re.search(r'data-hash="([^"]*)"', html)
    if not m:
        return None

    try:
        hash_val = m.group(1)
        embed_url = base64.b64decode(hash_val).decode("utf-8")
        referer = urllib.parse.urljoin(embed_url, "/")

        embed_html = http_get(embed_url)
        if not embed_html:
            return None
        pm = re.search(r'window\.__P="([^"]*)"', embed_html)
        if not pm:
            return None

        stream_json = deobfuscate_blob(pm.group(1))
        stream_data = json.loads(stream_json)
        master_m3u8 = stream_data.get("src")
        if not master_m3u8:
            return None

        # Subtitles
        sub_url = ""
        for s in stream_data.get("subtitles", []):
            if s.get("default") or s.get("lang") == "English":
                sub_url = s.get("src", "")
                break
        if not sub_url and stream_data.get("subtitles"):
            sub_url = stream_data["subtitles"][0].get("src", "")

        # Qualities
        target_url = master_m3u8
        try:
            m3u8_text = http_get(master_m3u8, headers={"Referer": referer})
            if m3u8_text:
                lines = m3u8_text.splitlines()
                qualities = []
                for i, line in enumerate(lines):
                    if line.startswith("#EXT-X-STREAM-INF"):
                        q_label = "Auto"
                        if "RESOLUTION=" in line:
                            q_label = line.split("RESOLUTION=")[1].split(",")[0].split("x")[-1] + "p"
                        if i + 1 < len(lines):
                            var_url = urllib.parse.urljoin(master_m3u8, lines[i + 1].strip())
                            qualities.append((q_label, var_url))
                if qualities:
                    pref = preferred_quality.lower().rstrip("p")
                    matched = [u for q, u in qualities if pref in q.lower()]
                    target_url = matched[0] if matched else qualities[0][1]
        except Exception:
            pass

        return {
            "video_url": target_url,
            "master_url": master_m3u8,
            "sub_url": sub_url,
            "referer": referer
        }
    except Exception:
        return None

def resolve_continue_target(query=None):
    """
    Finds the latest watched anime, season, episode, and timestamp.
    If the episode was completed (finished: true or watched > 90%), advances to the next episode.
    If the last episode was the season finale, advances to Season N+1 Episode 1.
    """
    data = load_resume_state()
    if not data:
        return None

    items = list(data.values())
    if query:
        q = query.lower().strip()
        items = [x for x in items if q in x.get("title", "").lower()]

    if not items:
        return None

    # Pick entry with latest updated_at
    latest = max(items, key=lambda x: x.get("updated_at", 0))
    raw_title = latest.get("title", "")
    anime_base, season, ep = parse_anime_title(raw_title)
    pos = float(latest.get("position", 0.0))
    dur = float(latest.get("duration", 0.0))
    finished = bool(latest.get("finished", False))

    is_completed = finished or (dur > 0 and pos >= (dur - 25.0))

    target_ep = ep
    target_season = season
    target_pos = 0.0

    if is_completed:
        # Move to next episode
        target_ep = ep + 1
        target_pos = 0.0

        # Check total episodes in this season to detect season completion
        search_q = f"{anime_base} Season {season}" if season > 1 else anime_base
        results = search_anime(search_q)
        if results:
            ep_list = get_episodes(results[0]["slug"])
            if ep_list:
                max_ep = len(ep_list)
                if target_ep > max_ep:
                    # Season completed! Advance to Season + 1
                    target_season = season + 1
                    target_ep = 1
    else:
        target_ep = ep
        target_season = season
        target_pos = max(0.0, pos - 2.0) if pos > 5.0 else 0.0

    search_title = f"{anime_base} Season {target_season}" if target_season > 1 else anime_base

    return {
        "search_title": search_title,
        "anime_base": anime_base,
        "season": target_season,
        "episode": target_ep,
        "timestamp": round(target_pos, 1),
        "time_str": format_time(target_pos),
        "original_title": raw_title,
        "was_completed": is_completed,
    }

def find_next_season(current_title, current_season):
    """
    Finds the next season (current_season + 1) for the given anime.
    """
    anime_base, _, _ = parse_anime_title(current_title)
    next_s_num = current_season + 1
    next_q = f"{anime_base} Season {next_s_num}"
    results = search_anime(next_q)
    if not results:
        # Search base anime to find sequels/movies
        results = search_anime(anime_base)

    if results:
        # Look for Season next_s_num
        for r in results:
            t = r["title"].lower()
            if f"season {next_s_num}" in t or f"s{next_s_num}" in t:
                eps = get_episodes(r["slug"])
                if eps:
                    return {
                        "search_title": r["title"],
                        "slug": r["slug"],
                        "season": next_s_num,
                        "episode": 1
                    }
        # Fallback to next result if current is Season 1
        if len(results) > 1 and current_season == 1:
            r = results[1]
            eps = get_episodes(r["slug"])
            if eps:
                return {
                    "search_title": r["title"],
                    "slug": r["slug"],
                    "season": 2,
                    "episode": 1
                }
    return None

def download_season(query, season_num=None, quality="1080p", out_dir=None):
    """
    Downloads an entire season of an anime.
    Smart enough to check resume_state.json and skip episodes you've completed!
    Also skips files already downloaded on disk.
    """
    search_q = query
    if season_num and int(season_num) > 1 and f"season {season_num}" not in query.lower():
        search_q = f"{query} Season {season_num}"

    print(f"\033[1;36m==>\033[0m Searching HiAnime for: \033[1;33m{search_q}\033[0m...", flush=True)
    results = search_anime(search_q)
    if not results:
        print(f"\033[1;31m[!] No anime found matching '{search_q}'.\033[0m", flush=True)
        return False

    target = results[0]
    anime_title = target["title"]
    print(f"\033[1;32m==>\033[0m Found: \033[1;37m{anime_title}\033[0m", flush=True)

    episodes = get_episodes(target["slug"])
    if not episodes:
        print("\033[1;31m[!] No episodes available to download.\033[0m", flush=True)
        return False

    total_eps = len(episodes)
    print(f"\033[1;32m==>\033[0m Season contains \033[1;36m{total_eps} episodes\033[0m.", flush=True)

    # Base download folder: ~/Videos/Anime/<Anime Title>/
    base_dir = out_dir or os.path.expanduser(f"~/Videos/Anime/{re.sub(r'[/\\?%*:|\"<>]', '_', anime_title)}")
    os.makedirs(base_dir, exist_ok=True)
    print(f"\033[1;34m==>\033[0m Destination: \033[1;35m{base_dir}\033[0m\n", flush=True)

    resume_data = load_resume_state()

    downloaded_count = 0
    skipped_count = 0

    for idx, ep in enumerate(episodes, 1):
        ep_num = ep["number"]
        ep_id = ep["id"]
        full_ep_title = f"{anime_title} Episode {ep_num}"
        out_filename = f"{anime_title} - Episode {ep_num:0>2}.mp4"
        out_path = os.path.join(base_dir, out_filename)

        # Check 1: Completed in resume_state.json
        is_completed = False
        for k, v in resume_data.items():
            if k.strip().lower() == full_ep_title.strip().lower():
                dur = float(v.get("duration", 0.0))
                pos = float(v.get("position", 0.0))
                if v.get("finished") or (dur > 0 and pos >= (dur - 25.0)):
                    is_completed = True
                    break

        if is_completed:
            print(f"\033[1;32m[✓]\033[0m Ep {ep_num}/{total_eps}: \033[2mAlready watched & completed in history. Skipping.\033[0m", flush=True)
            skipped_count += 1
            continue

        # Check 2: Already downloaded on disk (> 5MB)
        if os.path.exists(out_path) and os.path.getsize(out_path) > 5 * 1024 * 1024:
            print(f"\033[1;32m[✓]\033[0m Ep {ep_num}/{total_eps}: \033[2mFile already downloaded on disk. Skipping.\033[0m", flush=True)
            skipped_count += 1
            continue

        # Download needed
        print(f"\033[1;36m[↓]\033[0m Ep {ep_num}/{total_eps}: Resolving stream...", flush=True)
        stream_info = resolve_stream(ep_id, mode="sub", preferred_quality=quality)
        if not stream_info:
            print(f"\033[1;31m[!] Failed to resolve stream for Episode {ep_num}. Skipping.\033[0m", flush=True)
            continue

        vid_url = stream_info["video_url"]
        refr = stream_info["referer"]
        sub_url = stream_info.get("sub_url")

        # Download subtitles if present
        if sub_url:
            sub_path = out_path.rsplit(".", 1)[0] + ".vtt"
            try:
                sub_req = urllib.request.Request(sub_url, headers={"Referer": refr, "User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(sub_req, timeout=8) as sresp:
                    with open(sub_path, "wb") as sf:
                        sf.write(sresp.read())
            except Exception:
                pass

        print(f"\033[1;33m[↓]\033[0m Ep {ep_num}/{total_eps}: Downloading ({quality}, 16 parallel threads)...", flush=True)
        cmd = [
            "yt-dlp",
            "--referer", refr,
            "--no-skip-unavailable-fragments",
            "--fragment-retries", "infinite",
            "-N", "16",
            "-o", out_path,
            vid_url,
        ]
        ret = subprocess.run(cmd)
        if ret.returncode == 0:
            print(f"\033[1;32m[+] Successfully downloaded Episode {ep_num}!\033[0m\n", flush=True)
            downloaded_count += 1
        else:
            print(f"\033[1;31m[!] Error downloading Episode {ep_num}.\033[0m\n", flush=True)

    print(f"\n\033[1;32m==> Season download finished!\033[0m Downloaded: \033[1;36m{downloaded_count}\033[0m, Skipped: \033[1;33m{skipped_count}\033[0m (Total: {total_eps})", flush=True)
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: anicast_engine.py [continue|next-season|download|check-last-ep] [args...]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "continue":
        q = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else None
        target = resolve_continue_target(q)
        if target:
            print(json.dumps(target))
            sys.exit(0)
        else:
            sys.exit(1)

    elif cmd == "next-season":
        title = sys.argv[2] if len(sys.argv) > 2 else ""
        season = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else 1
        nxt = find_next_season(title, season)
        if nxt:
            print(json.dumps(nxt))
            sys.exit(0)
        else:
            sys.exit(1)

    elif cmd == "download":
        q = sys.argv[2] if len(sys.argv) > 2 else ""
        s = sys.argv[3] if len(sys.argv) > 3 else None
        quality = os.environ.get("ANI_CAST_QUALITY", "1080p")
        ok = download_season(q, season_num=s, quality=quality)
        sys.exit(0 if ok else 1)

    elif cmd == "check-last-ep":
        # Checks if title is the final episode of its season
        title = sys.argv[2] if len(sys.argv) > 2 else ""
        anime_base, season, ep = parse_anime_title(title)
        search_q = f"{anime_base} Season {season}" if season > 1 else anime_base
        results = search_anime(search_q)
        if results:
            eps = get_episodes(results[0]["slug"])
            if eps and ep >= len(eps):
                print(json.dumps({"is_last": True, "anime_base": anime_base, "season": season, "total": len(eps)}))
                sys.exit(0)
        print(json.dumps({"is_last": False}))
        sys.exit(0)
