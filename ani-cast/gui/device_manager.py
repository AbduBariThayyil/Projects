"""
Target device discovery and management.
Provides live mDNS discovery for Chromecast / Android TV devices
and explicit 'This Device (Local Screen / MPV)' support.
"""
import os
import json
import time
import threading
import gi

gi.require_version("GLib", "2.0")
from gi.repository import GLib

DEVICES_CACHE_FILE = os.path.expanduser("~/.local/state/ani-cast/discovered_devices.json")
LAST_DEVICE_FILE = os.path.expanduser("~/.local/state/ani-cast/last_device.txt")

LOCAL_DEVICE = {
    "name": "This Device (Local Screen / MPV)",
    "id": "local",
    "ip": "127.0.0.1",
    "model": "Local Screen",
    "is_local": True,
}


class DeviceManager:
    def __init__(self, on_update_callback=None):
        self.on_update_callback = on_update_callback
        self.devices = [dict(LOCAL_DEVICE)]
        self.selected_device_id = "local"
        self._load_cached_devices()
        self._load_last_selected()
        self._is_discovering = False
        self._browser = None
        self._zconf = None

    def _load_cached_devices(self):
        if os.path.exists(DEVICES_CACHE_FILE):
            try:
                with open(DEVICES_CACHE_FILE, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                    for d in cached:
                        dev = {
                            "name": d.get("name", "TV"),
                            "id": d.get("name", d.get("ip", "tv")),
                            "ip": d.get("ip", ""),
                            "model": d.get("model", "Cast Device"),
                            "is_local": False,
                        }
                        if not any(x["id"] == dev["id"] or x["ip"] == dev["ip"] for x in self.devices):
                            self.devices.append(dev)
            except Exception:
                pass

    def _save_cached_devices(self):
        try:
            os.makedirs(os.path.dirname(DEVICES_CACHE_FILE), exist_ok=True)
            cast_only = [
                {
                    "name": d["name"],
                    "ip": d["ip"],
                    "port": 8009,
                    "model": d.get("model", "Cast Device"),
                }
                for d in self.devices
                if not d.get("is_local")
            ]
            with open(DEVICES_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(cast_only, f, indent=2)
        except Exception:
            pass

    def _load_last_selected(self):
        saved = None
        if os.path.exists(LAST_DEVICE_FILE):
            try:
                with open(LAST_DEVICE_FILE, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        saved = content
            except Exception:
                pass

        if saved:
            if saved == "local" or any(d["id"] == saved or d["name"] == saved for d in self.devices):
                self.selected_device_id = saved
                return

        # No explicit user preference saved: default to TV if found, else local
        self._default_to_tv_or_local()

    def _default_to_tv_or_local(self):
        duaa = next((d for d in self.devices if not d.get("is_local") and "duaa" in d["name"].lower()), None)
        if duaa:
            self.selected_device_id = duaa["id"]
            return
        any_tv = next((d for d in self.devices if not d.get("is_local")), None)
        if any_tv:
            self.selected_device_id = any_tv["id"]
            return
        self.selected_device_id = "local"

    def save_selected_device(self, dev_id):
        self.selected_device_id = dev_id
        try:
            os.makedirs(os.path.dirname(LAST_DEVICE_FILE), exist_ok=True)
            with open(LAST_DEVICE_FILE, "w", encoding="utf-8") as f:
                f.write(dev_id + "\n")
        except Exception:
            pass

    def get_selected_device(self):
        for d in self.devices:
            if d["id"] == self.selected_device_id or d["name"] == self.selected_device_id:
                return d
        return self.devices[0]

    def set_selected_device(self, dev_id):
        self.save_selected_device(dev_id)

    def start_discovery(self, timeout=3.0):
        if self._is_discovering:
            return

        def _worker():
            self._is_discovering = True
            try:
                import zeroconf
                from pychromecast.discovery import CastBrowser, SimpleCastListener

                seen_hosts = {d["ip"] for d in self.devices if d.get("ip")}

                def add_cb(uuid, service):
                    dev = self._browser.devices.get(uuid)
                    if dev and dev.host and dev.host not in seen_hosts:
                        seen_hosts.add(dev.host)
                        new_dev = {
                            "name": dev.friendly_name or "TV",
                            "id": dev.friendly_name or dev.host,
                            "ip": dev.host,
                            "model": dev.model_name or "Cast Device",
                            "is_local": False,
                        }
                        # Update or add
                        existing = next((x for x in self.devices if x.get("ip") == dev.host), None)
                        if existing:
                            existing.update(new_dev)
                        else:
                            self.devices.append(new_dev)

                        self._save_cached_devices()
                        if not os.path.exists(LAST_DEVICE_FILE) and self.selected_device_id == "local":
                            self._default_to_tv_or_local()
                        if self.on_update_callback:
                            GLib.idle_add(self.on_update_callback, list(self.devices))

                self._zconf = zeroconf.Zeroconf()
                self._browser = CastBrowser(SimpleCastListener(add_cb), self._zconf)
                self._browser.start_discovery()

                # Run discovery
                start_t = time.time()
                while time.time() - start_t < timeout:
                    time.sleep(0.2)

                self._browser.stop_discovery()
                self._zconf.close()
            except Exception:
                pass
            finally:
                self._is_discovering = False
                if self.on_update_callback:
                    GLib.idle_add(self.on_update_callback, list(self.devices))

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
