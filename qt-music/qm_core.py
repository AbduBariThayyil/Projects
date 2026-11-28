#!/usr/bin/env python3
"""lyricview - native, GPU-rendered fullscreen lyrics with word-by-word animation (Qt Quick).

Follows whatever your MPRIS player is playing (Lollypop, mpv, Spotify, ...).
Lyrics: sidecar .lrc -> embedded tags (musicD writes both) -> lrclib.net (cached).
Needs: pyside6, playerctl  (sudo pacman -S pyside6 playerctl).  Optional: python-mutagen.

  lyricview                 fullscreen        lyricview -p lollypop   follow only that player
  lyricview --windowed      normal window     lyricview --lite        weak GPU: no drift/mask effects

Keys:  Space play/pause · ←/→ seek 5s · N/P next/prev · [ ] lyric timing ∓100ms · , . word spread
       F fullscreen · Q quit · click a line to jump · click the bar to seek
"""
from __future__ import annotations

import argparse
import ctypes
import fcntl
import hashlib
import io
import json
import os
os.environ.setdefault("QSG_RENDER_LOOP", "basic")
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CACHE = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "lyricview"
SEP = "\x1f"
FMT = SEP.join(["{{status}}", "{{playerName}}", "{{artist}}", "{{title}}", "{{album}}",
                "{{mpris:length}}", "{{xesam:url}}", "{{mpris:artUrl}}", "{{position}}"])
UA = "lyricview/1.0"


# ───────────────────────────── lyrics parsing ─────────────────────────────
TS = re.compile(r"\[(\d+):(\d+(?:[.:]\d+)?)\]")
WTS = re.compile(r"<(\d+):(\d+(?:\.\d+)?)>")
SPREAD = 1.0  # >1 stretches estimated word timing, <1 shortens
CJK = "\u2e80-\u9fff\uac00-\ud7af\uff00-\uffef"
TOKEN = re.compile(rf"([{CJK}]|[^\s{CJK}]+)(\s*)")


def _t(m, s):
    return int(m) * 60 + float(s.replace(":", "."))


def has_timestamps(text):
    return len(TS.findall(text or "")) >= 2


def build_words(body, t, end):
    """Split a lyric line into words with start/end times. Uses real <mm:ss.xx> word tags when present."""
    if WTS.search(body):
        parts = re.split(r"<(\d+):(\d+(?:\.\d+)?)>", body)
        stamps = [(_t(parts[i], parts[i + 1]), parts[i + 2]) for i in range(1, len(parts) - 2, 3)]
        if parts[0].strip():  # enhanced LRC: the first word has no <tag> - it starts at the line's own [mm:ss.xx]
            stamps.insert(0, (t, parts[0]))
        words = []
        for k, (ts, txt) in enumerate(stamps):
            te = stamps[k + 1][0] if k + 1 < len(stamps) else min(end, ts + 1.6)  # last word: don't crawl over a long gap
            w = txt.strip()
            if w:
                words.append({"t": round(ts, 3), "e": round(max(te, ts + 0.05), 3), "w": w,
                              "s": txt.endswith(" ") and k + 1 < len(stamps)})
        if words:
            return words
        body = WTS.sub("", body)
    toks = [(m.group(1), bool(m.group(2))) for m in TOKEN.finditer(body.strip())]
    if not toks:
        return []
    chars = sum(len(w) for w, _ in toks)
    # Singing time: a line normally fills (almost) its whole slot up to the next line, so slow songs
    # aren't rushed; only long instrumental gaps are capped. SPREAD (Qt app: , and . keys) scales it.
    gap = max(0.3, end - t)
    cap = max(4.5, 0.17 * chars + 1.0)
    dur = min(max(0.5, min(gap * 0.9, cap) * SPREAD), max(0.4, gap - 0.05))
    weights = [2.5 if re.match(rf"[{CJK}]", w) else len(w) + 1.2 for w, _ in toks]
    total, acc, words = sum(weights), 0.0, []
    for (w, sp), wt in zip(toks, weights):
        ws, we = t + dur * acc / total, t + dur * (acc + wt) / total
        acc += wt
        words.append({"t": round(ws, 3), "e": round(we, 3), "w": w, "s": sp})
    words[-1]["s"] = False
    return words


def parse_lrc(text, length=None):
    offset, raw = 0.0, []
    for ln in text.splitlines():
        ln = ln.strip()
        mo = re.match(r"\[offset:\s*([+-]?\d+)\]", ln, re.I)
        if mo:
            offset = int(mo.group(1)) / 1000
            continue
        stamps = TS.findall(ln)
        if stamps:
            body = TS.sub("", ln).strip()
            raw += [(max(0.0, _t(a, b) - offset), body) for a, b in stamps]
    raw.sort(key=lambda x: x[0])
    lines = []
    for i, (t, body) in enumerate(raw):
        if not body:
            continue
        end = raw[i + 1][0] if i + 1 < len(raw) else (length if length and length > t + 1 else t + 5)
        end = max(end, t + 0.3)
        words = build_words(body, t, end)
        if not words:
            continue
        lines.append({"t": round(t, 3), "e": round(end, 3), "words": words, "gap": False})
    # instrumental gaps -> animated dots
    out = []
    if lines and lines[0]["t"] > 6:
        out.append({"t": 0.5, "e": round(lines[0]["t"] - 0.4, 3), "words": [], "gap": True})
    for i, ln in enumerate(lines):
        out.append(ln)
        sung_end = ln["words"][-1]["e"]
        nxt = lines[i + 1]["t"] if i + 1 < len(lines) else None
        if nxt and nxt - sung_end > 6:
            out.append({"t": round(sung_end + 0.5, 3), "e": round(nxt - 0.4, 3), "words": [], "gap": True})
    return out


def parse_plain(text):
    return [{"text": ln.strip()} for ln in (text or "").splitlines()]


# ───────────────────────────── lyrics sources ─────────────────────────────
def http_get(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def path_from_url(url):
    if url and url.startswith("file://"):
        return Path(urllib.parse.unquote(urllib.parse.urlparse(url).path))
    return None


def tag_lyrics(path):
    try:
        import mutagen
        f = mutagen.File(path)
        if f is None:
            return None
        tags = f.tags
        if tags is None:
            return None
        if hasattr(tags, "getall"):  # ID3
            us = tags.getall("USLT")
            if us:
                return str(us[0].text)
        for k in ("\xa9lyr", "lyrics", "LYRICS", "UNSYNCEDLYRICS", "unsyncedlyrics"):
            if k in tags:
                v = tags[k]
                v = v[0] if isinstance(v, list) else v
                return str(v)
    except Exception:
        pass
    return None


def lrclib(artist, title, album, length):
    base, t = "https://lrclib.net/api/", re.sub(r"\s*[\(\[]\s*(?:feat|ft|with)\b[^\)\]]*[\)\]]", "", title, flags=re.I).strip() or title
    plain = None
    if album and length:
        try:
            d = json.loads(http_get(base + "get?" + urllib.parse.urlencode(
                {"artist_name": artist, "track_name": t, "album_name": album, "duration": int(round(length))}), 6))
            if d.get("syncedLyrics"):
                return d["syncedLyrics"]
            plain = d.get("plainLyrics")
        except Exception:
            pass
    for params in ({"track_name": t, "artist_name": artist}, {"q": f"{artist} {t}"}):
        try:
            items = json.loads(http_get(base + "search?" + urllib.parse.urlencode(params), 6))
        except Exception:
            continue
        good = [i for i in items if isinstance(i, dict) and (not length or not i.get("duration") or abs(i["duration"] - length) <= 6)]
        good.sort(key=lambda i: abs((i.get("duration") or length or 0) - (length or 0)))
        for i in good:
            if i.get("syncedLyrics"):
                return i["syncedLyrics"]
        plain = plain or next((i["plainLyrics"] for i in good if i.get("plainLyrics")), None)
    return plain


def load_lyrics(meta):
    """-> {'kind': synced|plain|none, 'lines': [...], 'src': str}"""
    length = meta["length"]
    path = path_from_url(meta["url"])
    text, src = None, ""
    if path:
        for cand in (path.with_suffix(".lrc"), path.with_suffix(".LRC")):
            if cand.exists():
                try:
                    text, src = cand.read_text("utf-8", "replace"), ".lrc file"
                    break
                except OSError:
                    pass
        if not text or not has_timestamps(text):
            t2 = tag_lyrics(path) if path.exists() else None
            if t2 and (has_timestamps(t2) or not text):
                text, src = t2, "embedded tags"
    if not text or not has_timestamps(text):
        ck = CACHE / "lyrics" / (meta["key"] + ".json")
        try:
            cached = json.loads(ck.read_text("utf-8"))
        except Exception:
            cached = None
        if cached is not None and cached.get("text") is None and time.time() - ck.stat().st_mtime > 7 * 86400:
            cached = None  # retry old misses after a week
        if cached is None:
            got = lrclib(meta["artist"], meta["title"], meta["album"], length)
            cached = {"text": got}
            try:  # misses are cached too, so we don't hammer lrclib on every play
                ck.parent.mkdir(parents=True, exist_ok=True)
                ck.write_text(json.dumps(cached), "utf-8")
            except OSError:
                pass
        if cached.get("text") and (has_timestamps(cached["text"]) or not text):
            text, src = cached["text"], "lrclib"
    wl = cached_wordlevel(meta)  # a word-by-word version found on an earlier play wins over line-level ones
    if wl and not re.search(r"<\d+:\d+(?:\.\d+)?>", text or ""):
        text, src = wl, "word-level (cached)"
    if not text or not text.strip():
        return {"kind": "none", "lines": [], "src": ""}
    if has_timestamps(text):
        lines = parse_lrc(text, length)
        if lines:
            return {"kind": "synced", "lines": lines, "src": src, "raw": text, "length": length,
                    "wordlevel": bool(re.search(r"<\d+:\d+(?:\.\d+)?>", text))}
    return {"kind": "plain", "lines": parse_plain(re.sub(r"\[[^\]]*\]", "", text)), "src": src}


# ───────────────────────────── artwork ─────────────────────────────
def load_art(meta):
    """-> (bytes, mime) or None"""
    url, path = meta["art"], path_from_url(meta["url"])
    if url:
        try:
            p = path_from_url(url)
            data = p.read_bytes() if p else http_get(url, 6)
            if data:
                return data, ("image/png" if data[:4] == b"\x89PNG" else "image/jpeg")
        except Exception:
            pass
    if path and path.exists():
        try:
            import mutagen
            f = mutagen.File(path)
            tags = getattr(f, "tags", None)
            if tags is not None and hasattr(tags, "getall") and tags.getall("APIC"):
                a = tags.getall("APIC")[0]
                return a.data, a.mime or "image/jpeg"
            if tags is not None and "covr" in tags:
                c = tags["covr"][0]
                return bytes(c), ("image/png" if bytes(c)[:4] == b"\x89PNG" else "image/jpeg")
            if getattr(f, "pictures", None):
                return f.pictures[0].data, f.pictures[0].mime
        except Exception:
            pass
        for name in ("cover", "folder", "front", "album", "Cover", "Folder"):
            for ext in ("jpg", "jpeg", "png"):
                c = path.parent / f"{name}.{ext}"
                if c.exists():
                    return c.read_bytes(), "image/png" if ext == "png" else "image/jpeg"
    return None




# ───────────────────────────── word-level lyrics (same sources as musicD) ─────────────────────────────
import unicodedata


def _wl_get(url, timeout=8, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": "lyricview/2", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _wl_json(url, timeout=8, headers=None):
    return json.loads(_wl_get(url, timeout, headers).decode("utf-8"))


def _wl_tokens(s):
    s = unicodedata.normalize("NFKD", s or "").lower()
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return set(re.sub(r"[^\w\s]", " ", s).split())


def _wl_clean(t):
    return re.sub(r"\s*[\(\[]\s*(?:official|lyrics?|audio|video|hd|4k|remaster(?:ed)?)[^\)\]]*[\)\]]", "", t or "", flags=re.I).strip()


_WL_TAG = re.compile(r"<(\d+):(\d+(?:\.\d+)?)>")


def _wl_level(text):
    if not text:
        return ""
    if _WL_TAG.search(text):
        return "word"
    return "line" if re.search(r"^\s*\[\d+:\d+", text, re.M) else "plain"


def _wl_stamp(sec):
    m = int(sec // 60)
    return f"{m:02d}:{sec - 60 * m:05.2f}"


def _wl_enh(lines):
    """[(line_start, [(word_start, text)])] -> enhanced LRC (what lyricview reads)."""
    return "\n".join(f"[{_wl_stamp(ls)}]" + "".join(f"<{_wl_stamp(ws)}>{wt}" for ws, wt in words) for ls, words in lines)


def _wl_yrc(text):
    """NetEase word-level format:  [startMs,durMs](wordStartMs,wordDurMs,0)word ..."""
    lines = []
    for raw in (text or "").splitlines():
        m = re.match(r"^\[(\d+),\d+\](.*)$", raw)
        if not m:
            continue
        words = [(int(a) / 1000, w) for a, w in re.findall(r"\((\d+),\d+,\d+\)(.*?)(?=\(\d+,\d+,\d+\)|$)", m.group(2), re.S)]
        words = [(t, w) for t, w in words if w != ""]
        if words:
            lines.append((int(m.group(1)) / 1000, words))
    return _wl_enh(lines) if lines else None


def _wl_ttime(v):
    v = v.strip()
    if v.endswith("ms"):
        return float(v[:-2]) / 1000
    if v.endswith("s"):
        return float(v[:-1])
    sec = 0.0
    for p in v.split(":"):
        sec = sec * 60 + float(p)
    return sec


def _wl_ttml(ttml):
    """Apple-style TTML with <span begin=..> per word/syllable -> enhanced LRC."""
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(ttml.strip())
    except ET.ParseError:
        return None
    local = lambda e: e.tag.rsplit("}", 1)[-1]
    lines = []
    for p in root.iter():
        if local(p) != "p":
            continue
        words = []
        for sp in p.iter():
            if local(sp) != "span" or len(sp) or not sp.get("begin") or not (sp.text or "").strip():
                continue
            txt = sp.text
            if sp.tail and (sp.tail[:1].isspace() or sp.tail.strip()):
                txt = txt.rstrip() + " "
            words.append((_wl_ttime(sp.get("begin")), txt.replace("\n", " ")))
        if words:
            lines.append((_wl_ttime(p.get("begin")) if p.get("begin") else words[0][0], words))
    return _wl_enh(lines) if lines else None


def _wl_plausible(text, duration):
    stamps = [int(m) * 60 + float(sec) for m, sec in re.findall(r"^\[(\d+):(\d+(?:\.\d+)?)\]", text, re.M)]
    if len(stamps) < 3:
        return False
    return not duration or max(stamps) <= duration + 15


def _wl_src_netease(artist, title, album, dur):
    h = {"Referer": "https://music.163.com/", "User-Agent": "Mozilla/5.0"}
    j = _wl_json("https://music.163.com/api/search/get/web?" + urllib.parse.urlencode(
        {"s": f"{artist} {title}".strip(), "type": 1, "offset": 0, "limit": 10, "total": "true"}), 8, h)
    tt, aa = _wl_tokens(_wl_clean(title)), _wl_tokens(artist)
    for song in (j.get("result") or {}).get("songs") or []:
        st, sa = _wl_tokens(song.get("name", "")), _wl_tokens(" ".join(a.get("name", "") for a in song.get("artists") or []))
        if not tt or len(tt & st) / len(tt) < 0.6 or (aa and not (aa & sa)):
            continue
        if dur and song.get("duration") and abs(song["duration"] / 1000 - dur) > 4:
            continue
        lj = _wl_json(f"https://music.163.com/api/song/lyric?id={song['id']}&lv=1&kv=1&tv=-1&yv=1", 8, h)
        got = _wl_yrc((lj.get("yrc") or {}).get("lyric"))
        if got:
            return got
    return None


def _wl_src_betterlyrics(artist, title, album, dur):
    q = {"s": title, "a": artist}
    if album:
        q["al"] = album
    if dur:
        q["d"] = int(round(dur))
    raw = _wl_get("https://lyrics-api.boidu.dev/getLyrics?" + urllib.parse.urlencode(q), 10).decode("utf-8", "replace").strip()
    if raw.startswith("{"):  # JSON wrapper
        j = json.loads(raw)
        raw = (j.get("ttml") or j.get("lyrics") or "") if isinstance(j, dict) else ""
    return _wl_ttml(raw) if raw.startswith("<") else None


def _wl_src_syncedlyrics(artist, title, album, dur):
    try:
        import syncedlyrics
    except ImportError:
        return None
    for prov in ("Musixmatch", "NetEase"):
        txt = syncedlyrics.search(f"{title} {artist}", enhanced=True, providers=[prov])
        if txt and _wl_level(txt) == "word":
            return txt
    return None


_WL_SOURCES = (("NetEase", _wl_src_netease), ("BetterLyrics", _wl_src_betterlyrics), ("syncedlyrics", _wl_src_syncedlyrics))


def _wl_variants(artist, title):
    t0 = _wl_clean(title)
    t1 = re.sub(r"\s*[\(\[]\s*(?:feat|ft|with)\b[^\)\]]*[\)\]]", "", t0, flags=re.I).strip()
    t2 = re.sub(r"\s*-\s*(?:\d{4}\s*)?(?:remaster(?:ed)?|radio edit|single version|album version|mono|stereo).*$", "", t1, flags=re.I).strip()
    out = []
    for t in (title, t1, t2):
        if t and (artist, t) not in out:
            out.append((artist, t))
    return out


def _wl_retry(fn, tries=3, delay=0.7):
    """Retry only on errors (network); an empty answer means 'not there' and is not retried."""
    for k in range(tries):
        try:
            return fn()
        except Exception:
            if k + 1 < tries:
                time.sleep(delay * (k + 1))
    return None



_wl_miss = {}


def wl_fetch(artist, title, album, length, budget=15):
    deadline = time.time() + budget
    for _name, fn in _WL_SOURCES:
        for a, t in _wl_variants(artist, title):
            if time.time() > deadline:
                return None
            got = _wl_retry(lambda: fn(a, t, album, length), tries=2)
            if got and _wl_level(got) == "word" and _wl_plausible(got, length):
                return got
    return None


def upgrade_lyrics(meta, lyr):
    """Lyrics that aren't word-by-word are looked up again on every play. -> a better lyrics dict, or None."""
    if lyr.get("kind") == "synced" and lyr.get("wordlevel"):
        return None
    # Always check online word-level providers on every play when lyrics lack word timestamps
    text = wl_fetch(meta["artist"], meta["title"], meta["album"], meta["length"], budget=10)
    if not text:
        return None
    try:
        ck = CACHE / "lyrics" / (meta["key"] + ".wl.json")
        ck.parent.mkdir(parents=True, exist_ok=True)
        ck.write_text(json.dumps({"text": text}), "utf-8")
    except OSError:
        pass
    lines = parse_lrc(text, meta["length"])
    return {"kind": "synced", "lines": lines, "src": "word-level", "raw": text, "length": meta["length"], "wordlevel": True} if lines else None


def cached_wordlevel(meta):
    try:
        return json.loads((CACHE / "lyrics" / (meta["key"] + ".wl.json")).read_text("utf-8")).get("text")
    except Exception:
        return None



import importlib.util
import random

AUDIO_EXT = {".mp3", ".m4a", ".flac", ".ogg", ".opus", ".wav", ".aac", ".wma", ".mp4"}


def _uri_from_path(p):
    """Convert a local filesystem path to a file:// URI without requiring Qt."""
    try:
        return Path(p).resolve().as_uri()
    except Exception:
        return "file://" + urllib.parse.quote(os.path.abspath(str(p)))



def _num(s):
    m = re.match(r"\d+", str(s or ""))
    return int(m.group()) if m else 0



class Library:
    """Scans the music folder (mutagen tags, cached by mtime+size) and indexes albums and artists."""

    def __init__(self, root):
        self.root = Path(root).expanduser()
        self.cache = CACHE / "library.json"
        self.tracks, self.albums, self.artists = [], {}, {}
        self.ready, self.count, self.pending, self.by_path, self._sigs = False, 0, None, {}, None

    @staticmethod
    def _read(p):
        title = artist = album = aart = year = ""
        tno = disc = 0
        length = 0.0
        try:
            import mutagen
            f = mutagen.File(p, easy=True)
            if f is not None:
                length = float(getattr(f.info, "length", 0) or 0)
                t = f.tags or {}

                def g(k):
                    v = t.get(k)
                    return str(v[0]).strip() if v else ""
                title, artist, album, aart = g("title"), g("artist"), g("album"), g("albumartist")
                tno, disc, year = _num(g("tracknumber")), _num(g("discnumber")), g("date")[:4]
        except Exception:
            pass
        pp = Path(p)  # fallback for untagged files: Artist/Album/Title.ext (the musicD layout)
        return {"path": p, "title": title or pp.stem, "artist": artist or (pp.parent.parent.name if len(pp.parts) > 2 else "Unknown Artist"),
                "album": album or pp.parent.name, "aartist": aart or artist or (pp.parent.parent.name if len(pp.parts) > 2 else "Unknown Artist"),
                "no": tno, "disc": disc, "len": length, "year": year}

    def load_cache(self):
        """Instant start from the last scan (stale entries are skipped at play time)."""
        try:
            data = json.loads(self.cache.read_text("utf-8"))
            ok = {p: v for p, v in data.items() if os.path.exists(p)}
            recs = [v[1] for v in ok.values()]
            if recs:
                self._index(recs)
                self._sigs = {p: v[0] for p, v in ok.items()}
        except Exception:
            pass

    def scan(self, progress=None):
        try:
            cached = json.loads(self.cache.read_text("utf-8"))
        except Exception:
            cached = {}
        fresh, recs, n = {}, [], 0
        for dp, dn, fn in os.walk(self.root):
            dn[:] = sorted(d for d in dn if not d.startswith("."))
            for f in sorted(fn):
                if os.path.splitext(f)[1].lower() not in AUDIO_EXT:
                    continue
                p = os.path.join(dp, f)
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                sig = [int(st.st_mtime), st.st_size]
                c = cached.get(p)
                rec = c[1] if c and c[0] == sig else self._read(p)
                fresh[p] = [sig, rec]
                recs.append(rec)
                n += 1
                if progress and n % 100 == 0:
                    progress(n)
        sigs = {p: v[0] for p, v in fresh.items()}
        self.pending = None if sigs == self._sigs else recs  # applied on the UI thread (apply_pending), never mid-playback
        self._sigs = sigs
        try:
            CACHE.mkdir(parents=True, exist_ok=True)
            tmp = self.cache.with_suffix(".tmp")
            tmp.write_text(json.dumps(fresh), "utf-8")  # ascii-escaped: odd filenames can't break the cache
            os.replace(tmp, self.cache)
        except OSError:
            pass

    def apply_pending(self):
        if self.pending is not None:
            self._index(self.pending)
            self.pending = None

    def _index(self, recs):
        albums = {}
        for t in recs:
            albums.setdefault((t["aartist"].lower(), t["album"].lower()), []).append(t)
        tracks, alb, art = [], {}, {}
        for aid, (key, ts) in enumerate(sorted(albums.items())):
            ts.sort(key=lambda t: (t["disc"], t["no"], t["title"].lower()))
            idxs = []
            for t in ts:
                t["i"] = len(tracks)
                idxs.append(t["i"])
                tracks.append(t)
            a = {"id": aid, "name": ts[0]["album"], "artist": ts[0]["aartist"], "year": next((t["year"] for t in ts if t["year"]), ""), "tracks": idxs}
            alb[aid] = a
            art.setdefault(ts[0]["aartist"].lower(), {"name": ts[0]["aartist"], "albums": []})["albums"].append(aid)
        for k, (_, v) in enumerate(sorted(art.items())):
            v["id"] = k
        self.tracks, self.albums = tracks, alb
        self.artists = {v["id"]: v for v in art.values()}
        self.count, self.ready = len(tracks), bool(tracks)
        self.by_path = {t["path"]: t["i"] for t in tracks}

    def artist_tracks(self, artist_id):
        a = self.artists.get(artist_id)
        if not a:
            return []
        albs = sorted(a["albums"], key=lambda i: (self.albums[i]["year"] or "9999", self.albums[i]["name"].lower()))
        return [t for i in albs for t in self.albums[i]["tracks"]]

    def album_list(self):
        return [{"id": a["id"], "name": a["name"], "sub": a["artist"] + (f" · {a['year']}" if a["year"] else ""), "n": len(a["tracks"])}
                for a in sorted(self.albums.values(), key=lambda a: (a["artist"].lower(), a["year"] or "9999", a["name"].lower()))]

    def artist_list(self):
        return [{"id": a["id"], "name": a["name"], "sub": f"{len(a['albums'])} album{'s' if len(a['albums']) != 1 else ''}",
                 "n": sum(len(self.albums[i]["tracks"]) for i in a["albums"])}
                for a in sorted(self.artists.values(), key=lambda a: a["name"].lower())]


def repair_audio(path):
    """Re-encode to a clean mp3 (drops attached pictures, fixes odd timestamps) for files QtMultimedia can't demux."""
    ff = shutil.which("ffmpeg")
    if not ff:
        return None
    st = os.stat(path)
    out = CACHE / "fixed" / (hashlib.md5(f"{path}|{st.st_mtime_ns}".encode()).hexdigest()[:16] + ".mp3")
    if out.exists():
        return str(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([ff, "-v", "error", "-y", "-i", path, "-vn", "-map_metadata", "-1", "-c:a", "libmp3lame", "-q:a", "2", str(out)],
                       capture_output=True, timeout=180)
    for old in sorted(out.parent.glob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True)[60:]:
        old.unlink(missing_ok=True)
    return str(out) if r.returncode == 0 and out.exists() and out.stat().st_size > 1000 else None


class Shuffler:
    """Random album -> random song of it -> crossed off; next time a random album again (the same album may
    come back while it still has songs left). Played songs are remembered by path, so rescans and songs you
    pick yourself stay crossed off; when everything has been played the list starts over."""

    def __init__(self, lib):
        self.lib, self.left, self.played = lib, {}, set()

    def reset(self):
        self.played.clear()
        self.left.clear()

    def _pool(self):
        t = self.lib.tracks
        pool = {aid: [i for i in a["tracks"] if t[i]["path"] not in self.played] for aid, a in self.lib.albums.items()}
        return {k: v for k, v in pool.items() if v}

    def mark(self, i):
        """Cross a song off (it was played, however it got started)."""
        self.played.add(self.lib.tracks[i]["path"])
        for aid in list(self.left):
            if i in self.left[aid]:
                self.left[aid].remove(i)
            if not self.left[aid]:
                del self.left[aid]

    def next(self):
        if not self.left:
            self.left = self._pool()
            if not self.left:  # everything has been played: start over
                self.played.clear()
                self.left = self._pool()
        if not self.left:
            return None
        aid = random.choice(list(self.left))
        i = self.left[aid][random.randrange(len(self.left[aid]))]
        self.mark(i)
        return i



# ───── online mode: search + stream from YouTube Music (ytmusicapi for search/radio, yt-dlp for the audio URL)
class _NoLog:
    def debug(self, m): pass
    def info(self, m): pass
    def warning(self, m): pass
    def error(self, m): pass


_YTM_API, _STREAMS, _FAKE = None, {}, bool(os.environ.get("LYRICVIEW_FAKE_ONLINE"))  # _FAKE: offline test double


def online_available():
    return _FAKE or (importlib.util.find_spec("ytmusicapi") is not None and importlib.util.find_spec("yt_dlp") is not None)


def _ytm():
    global _YTM_API
    if _YTM_API is None:
        from ytmusicapi import YTMusic
        _YTM_API = YTMusic()
    return _YTM_API


def _sq(url):
    return re.sub(r"=w\d+-h\d+.*$", "=w600-h600-l90-rj", url) if "googleusercontent" in url else url


def _secs(s):
    try:
        return float(sum(int(p) * 60 ** k for k, p in enumerate(reversed(str(s).split(":")))))
    except ValueError:
        return 0.0


def _item(vid, title, artists, album, length, thumbs):
    return {"id": vid, "title": title or "", "artist": (artists[0] if artists else "Unknown"), "artists": ", ".join(artists),
            "album": album or "", "len": float(length or 0), "art": _sq(thumbs[-1]["url"]) if thumbs else ""}


def yt_search(query, kind="songs", limit=15):
    if _FAKE:
        if kind == "albums":
            return [{"id": f"fake_alb_{i}", "title": f"{query.title()} Album {i}", "artist": "Fake Artist", "artists": "Fake Artist",
                     "album": f"{query.title()} Album {i}", "len": 0, "art": "", "is_album": True} for i in range(1, 6)]
        return [_item(f"fake{i}", f"{query.title()} Song {i}", ["Fake Artist"], "Fake Album", 30 + i, []) for i in range(1, 6)]
    out = []
    try:
        filt = "albums" if kind == "albums" else "songs"
        res = _ytm().search(query, filter=filt, limit=limit)
        for r in res:
            if kind == "albums" and r.get("browseId"):
                artists = [a["name"] for a in r.get("artists") or [] if a.get("name")]
                out.append({"id": r["browseId"], "title": r.get("title") or "", "artist": (artists[0] if artists else "Unknown"),
                            "artists": ", ".join(artists), "album": r.get("title") or "", "len": 0,
                            "art": _sq(r["thumbnails"][-1]["url"]) if r.get("thumbnails") else "", "is_album": True})
            elif r.get("videoId"):
                out.append(_item(r["videoId"], r.get("title"), [a["name"] for a in r.get("artists") or [] if a.get("name")],
                                 (r.get("album") or {}).get("name"), r.get("duration_seconds"), r.get("thumbnails") or []))
    except Exception:
        pass
    return out


def yt_album_tracks(browse_id):
    if _FAKE:
        return [_item(f"fake_track_{i}", f"Album Track {i}", ["Fake Artist"], "Album", 45 + i, []) for i in range(1, 7)]
    out = []
    try:
        alb = _ytm().get_album(browse_id)
        alb_name = alb.get("title") or ""
        alb_art = _sq(alb["thumbnails"][-1]["url"]) if alb.get("thumbnails") else ""
        for t in alb.get("tracks") or []:
            if t.get("videoId"):
                artists = [a["name"] for a in t.get("artists") or [] if a.get("name")]
                item = _item(t["videoId"], t.get("title"), artists, alb_name, t.get("duration_seconds") or _secs(t.get("length")), [])
                if alb_art:
                    item["art"] = alb_art
                out.append(item)
    except Exception:
        pass
    return out


def yt_radio(vid, limit=25):
    if _FAKE:
        return [_item(f"radio{i}", f"Similar Song {i}", ["Radio Artist"], "Radio Album", 25 + i, []) for i in range(1, 6)]
    wp = _ytm().get_watch_playlist(videoId=vid, radio=True, limit=limit)
    return [_item(t["videoId"], t.get("title"), [a["name"] for a in t.get("artists") or [] if a.get("name")],
                  (t.get("album") or {}).get("name"), _secs(t.get("length")), t.get("thumbnail") or [])
            for t in wp.get("tracks") or [] if t.get("videoId") and t["videoId"] != vid]


def resolve_stream(vid):
    """Direct audio URL for a video (yt-dlp, no download). Cached for a while - URLs stay valid for hours."""
    if _FAKE:
        return "http://fake.invalid/" + vid
    c = _STREAMS.get(vid)
    if c and time.time() - c[1] < 1200:
        return c[0]
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "noplaylist": True, "skip_download": True, "logger": _NoLog(),
            "format": "bestaudio[ext=m4a]/bestaudio/best", "socket_timeout": 15}
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info("https://www.youtube.com/watch?v=" + vid, download=False)
    url = info.get("url") or next((f["url"] for f in reversed(info.get("formats") or []) if f.get("url") and f.get("acodec") != "none"), "")
    if not url:
        raise RuntimeError("no audio stream")
    _STREAMS[vid] = (url, time.time())
    return url





_BGTYPES = ["clouds", "backdrop", "video", "image", "none"]


def _normalize_settings(raw):
    """Normalize legacy/corrupt settings values (e.g. bgType=0, bgDim=0) into valid UI settings."""
    cfg = dict(raw or {})
    bt = cfg.get("bgType")
    if isinstance(bt, (int, float)) and not isinstance(bt, bool):
        idx = int(bt)
        cfg["bgType"] = _BGTYPES[idx] if 0 <= idx < len(_BGTYPES) else "clouds"
    elif bt in ("0", "", None) or bt not in _BGTYPES:
        cfg["bgType"] = "clouds"
    bd = cfg.get("bgDim")
    try:
        bdf = float(bd)
    except (TypeError, ValueError):
        bdf = 0.65
    cfg["bgDim"] = 0.65 if bdf <= 0.05 else max(0.1, min(1.0, round(bdf, 2)))
    if not isinstance(cfg.get("keybinds"), dict):
        cfg["keybinds"] = {}
    return cfg


