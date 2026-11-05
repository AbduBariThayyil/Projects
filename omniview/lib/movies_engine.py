#!/usr/bin/env python3
"""
OmniView Movies & TV Shows Engine
Provides search, season/episode resolution, and stream generation
for mainstream movies and TV shows via IMDb, TVMaze, and multi-source streaming resolvers.
"""
import os
import sys
import json
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Any

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/html, */*",
}

# Fallback open streams for testing/preview when external providers are blocked
OPEN_STREAMS = [
    {
        "title": "Tears of Steel (Sci-Fi 4K/1080p)",
        "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4",
        "referer": "https://commondatastorage.googleapis.com",
    },
    {
        "title": "Big Buck Bunny (Animation 1080p)",
        "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
        "referer": "https://commondatastorage.googleapis.com",
    },
]


def http_get(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 5, is_json: bool = True) -> Any:
    req_headers = dict(DEFAULT_HEADERS)
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            if is_json:
                return json.loads(data.decode("utf-8", errors="ignore"))
            return data.decode("utf-8", errors="ignore")
    except Exception:
        return None


def search_movies_and_shows(query: str) -> List[Dict[str, Any]]:
    """
    Searches movies and TV series across IMDb auto-suggest and TVMaze.
    Returns list of dicts with keys: {id, title, year, type, poster, cast}.
    """
    if not query or not query.strip():
        return []

    q_clean = query.strip()
    first_char = q_clean[0].lower()
    if not first_char.isalnum():
        first_char = "a"

    encoded = urllib.parse.quote(q_clean.lower().replace(" ", "_"))
    imdb_url = f"https://v3.sg.media-imdb.com/suggestion/{first_char}/{encoded}.json"

    results: List[Dict[str, Any]] = []
    seen_ids = set()

    # 1. Primary: Query IMDb Suggest API
    data = http_get(imdb_url, timeout=4, is_json=True)
    if data and "d" in data:
        for item in data.get("d", []):
            qid = item.get("qid", "")
            media_type = "movie"
            if qid in ["tvSeries", "tvMiniSeries", "tvMovie", "tvSpecial"]:
                media_type = "tv"
            elif qid not in ["movie", "feature"]:
                continue

            imdb_id = item.get("id", "")
            if not imdb_id or imdb_id in seen_ids:
                continue

            seen_ids.add(imdb_id)
            poster_url = None
            if item.get("i"):
                poster_url = item["i"].get("imageUrl")

            results.append({
                "id": imdb_id,
                "title": item.get("l", "Unknown Title"),
                "year": item.get("y", "N/A"),
                "type": media_type,
                "poster": poster_url,
                "cast": item.get("s", ""),
            })

    # 2. Secondary fallback for TV Shows: TVMaze Search if query has few/no results
    if len(results) < 3:
        tvmaze_url = f"https://api.tvmaze.com/search/shows?q={urllib.parse.quote(q_clean)}"
        tv_data = http_get(tvmaze_url, timeout=4, is_json=True)
        if tv_data and isinstance(tv_data, list):
            for entry in tv_data:
                show = entry.get("show", {})
                title = show.get("name")
                if not title:
                    continue
                imdb_code = show.get("externals", {}).get("imdb") or f"tvm_{show.get('id')}"
                if imdb_code in seen_ids:
                    continue
                seen_ids.add(imdb_code)

                prem = show.get("premiered")
                year = prem.split("-")[0] if prem else "N/A"
                img = show.get("image", {})
                poster = img.get("original") or img.get("medium") if img else None

                results.append({
                    "id": imdb_code,
                    "tvmaze_id": show.get("id"),
                    "title": title,
                    "year": year,
                    "type": "tv",
                    "poster": poster,
                    "cast": ", ".join(show.get("genres", [])) or "TV Series",
                })

    return results


def get_tv_seasons_and_episodes(imdb_id: str, title: Optional[str] = None) -> Dict[int, List[Dict[str, Any]]]:
    """
    Fetches seasons and episodes list for a TV show by IMDb ID or title via TVMaze.
    Returns a dict mapping season_number -> list of episode dicts:
    {
      1: [
        {"season": 1, "number": 1, "title": "Pilot", "id": "1234", "summary": "..."},
        ...
      ]
    }
    """
    seasons: Dict[int, List[Dict[str, Any]]] = {}
    tvmaze_show_id = None

    # Step 1: Lookup by IMDb ID
    if imdb_id and imdb_id.startswith("tt"):
        lookup_url = f"https://api.tvmaze.com/lookup/shows?imdb={imdb_id}"
        show_obj = http_get(lookup_url, timeout=4, is_json=True)
        if show_obj and "id" in show_obj:
            tvmaze_show_id = show_obj["id"]

    # Step 2: Fallback lookup by title
    if not tvmaze_show_id and title:
        q_enc = urllib.parse.quote(title.strip())
        search_url = f"https://api.tvmaze.com/search/shows?q={q_enc}"
        search_data = http_get(search_url, timeout=4, is_json=True)
        if search_data and isinstance(search_data, list) and len(search_data) > 0:
            tvmaze_show_id = search_data[0].get("show", {}).get("id")

    # Step 3: Fetch episodes for this show
    if tvmaze_show_id:
        eps_url = f"https://api.tvmaze.com/shows/{tvmaze_show_id}/episodes"
        eps_data = http_get(eps_url, timeout=5, is_json=True)
        if eps_data and isinstance(eps_data, list):
            for ep in eps_data:
                s_num = ep.get("season", 1)
                e_num = ep.get("number", 1)
                name = ep.get("name") or f"Episode {e_num}"
                ep_obj = {
                    "season": s_num,
                    "number": e_num,
                    "title": name,
                    "id": f"{imdb_id}_s{s_num}e{e_num}",
                    "airdate": ep.get("airdate", ""),
                    "summary": ep.get("summary", ""),
                }
                seasons.setdefault(s_num, []).append(ep_obj)

    # Step 4: Graceful fallback if TVMaze has no listing
    if not seasons:
        # Default placeholder Season 1 (12 episodes) so user can still select and stream
        default_eps = []
        for i in range(1, 13):
            default_eps.append({
                "season": 1,
                "number": i,
                "title": f"Episode {i}",
                "id": f"{imdb_id}_s1e{i}",
                "airdate": "",
                "summary": "",
            })
        seasons[1] = default_eps

    return seasons


def resolve_movie_stream(imdb_id: str, title: Optional[str] = None) -> Dict[str, Any]:
    """
    Resolves streaming video URL and playback metadata for a Movie.
    Returns:
    {
        "video_url": "...",
        "master_url": "...",
        "referer": "...",
        "headers": {...},
        "sub_url": "...",
        "title": "..."
    }
    """
    clean_title = title.strip() if title else f"Movie {imdb_id}"

    # Embed/stream providers
    providers = [
        {
            "name": "VidSrc SU",
            "url": f"https://vidsrc.su/embed/movie/{imdb_id}",
            "referer": "https://vidsrc.su",
        },
        {
            "name": "AutoEmbed",
            "url": f"https://player.autoembed.cc/embed/movie/{imdb_id}",
            "referer": "https://player.autoembed.cc",
        },
        {
            "name": "MultiEmbed",
            "url": f"https://multiembed.mov/?video_id={imdb_id}",
            "referer": "https://multiembed.mov",
        },
        {
            "name": "VidSrc XYZ",
            "url": f"https://vidsrc.xyz/embed/movie?imdb={imdb_id}",
            "referer": "https://vidsrc.xyz",
        },
    ]

    selected = providers[0]
    return {
        "video_url": selected["url"],
        "master_url": selected["url"],
        "referer": selected["referer"],
        "headers": {
            "User-Agent": USER_AGENT,
            "Referer": selected["referer"],
        },
        "sub_url": "",
        "title": clean_title,
        "media_type": "movie",
        "imdb_id": imdb_id,
        "providers": providers,
    }


def resolve_tv_stream(imdb_id: str, season: int = 1, episode: int = 1, title: Optional[str] = None) -> Dict[str, Any]:
    """
    Resolves streaming video URL and playback metadata for a TV Show episode.
    """
    full_title = f"{title} S{season:02d}E{episode:02d}" if title else f"TV {imdb_id} S{season}E{episode}"

    providers = [
        {
            "name": "VidSrc SU",
            "url": f"https://vidsrc.su/embed/tv/{imdb_id}/{season}/{episode}",
            "referer": "https://vidsrc.su",
        },
        {
            "name": "AutoEmbed",
            "url": f"https://player.autoembed.cc/embed/tv/{imdb_id}/{season}/{episode}",
            "referer": "https://player.autoembed.cc",
        },
        {
            "name": "MultiEmbed",
            "url": f"https://multiembed.mov/?video_id={imdb_id}&s={season}&e={episode}",
            "referer": "https://multiembed.mov",
        },
        {
            "name": "VidSrc XYZ",
            "url": f"https://vidsrc.xyz/embed/tv?imdb={imdb_id}&season={season}&episode={episode}",
            "referer": "https://vidsrc.xyz",
        },
    ]

    selected = providers[0]
    return {
        "video_url": selected["url"],
        "master_url": selected["url"],
        "referer": selected["referer"],
        "headers": {
            "User-Agent": USER_AGENT,
            "Referer": selected["referer"],
        },
        "sub_url": "",
        "title": full_title,
        "media_type": "tv",
        "imdb_id": imdb_id,
        "season": season,
        "episode": episode,
        "providers": providers,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: movies_engine.py [search|seasons|resolve-movie|resolve-tv] [args...]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "search":
        q = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "Inception"
        res = search_movies_and_shows(q)
        print(json.dumps(res, indent=2))

    elif cmd == "seasons":
        imdb_id = sys.argv[2] if len(sys.argv) > 2 else "tt0903747"
        title = sys.argv[3] if len(sys.argv) > 3 else "Breaking Bad"
        seasons = get_tv_seasons_and_episodes(imdb_id, title)
        print(json.dumps({str(k): v for k, v in seasons.items()}, indent=2))

    elif cmd == "resolve-movie":
        imdb_id = sys.argv[2] if len(sys.argv) > 2 else "tt1375666"
        title = sys.argv[3] if len(sys.argv) > 3 else "Inception"
        info = resolve_movie_stream(imdb_id, title)
        print(json.dumps(info, indent=2))

    elif cmd == "resolve-tv":
        imdb_id = sys.argv[2] if len(sys.argv) > 2 else "tt0903747"
        s = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        e = int(sys.argv[4]) if len(sys.argv) > 4 else 1
        title = sys.argv[5] if len(sys.argv) > 5 else "Breaking Bad"
        info = resolve_tv_stream(imdb_id, s, e, title)
        print(json.dumps(info, indent=2))
