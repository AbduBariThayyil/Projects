"""
Async image caching and loading for GTK 4 textures.
"""
import os
import hashlib
import threading
import urllib.request
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, Gio, GLib

CACHE_DIR = os.path.expanduser("~/.cache/ani-cast/posters")
os.makedirs(CACHE_DIR, exist_ok=True)

_memory_cache = {}


def _url_to_path(url: str) -> str:
    h = hashlib.md5(url.encode("utf-8")).hexdigest()
    return os.path.join(CACHE_DIR, f"{h}.jpg")


def load_texture_async(url: str, callback, target_width=None, target_height=None):
    """
    Downloads and decodes image asynchronously.
    Calls `callback(texture)` on the main GLib thread via GLib.idle_add.
    """
    if not url:
        GLib.idle_add(callback, None)
        return

    if url in _memory_cache:
        GLib.idle_add(callback, _memory_cache[url])
        return

    file_path = _url_to_path(url)

    def _worker():
        try:
            if not os.path.exists(file_path) or os.path.getsize(file_path) < 100:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                        "Referer": "https://hianime.at/",
                    },
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = resp.read()
                    temp_path = f"{file_path}.tmp.{os.getpid()}"
                    with open(temp_path, "wb") as f:
                        f.write(data)
                    os.replace(temp_path, file_path)

            gfile = Gio.File.new_for_path(file_path)
            texture = Gdk.Texture.new_from_file(gfile)
            _memory_cache[url] = texture
            GLib.idle_add(callback, texture)
        except Exception:
            GLib.idle_add(callback, None)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
