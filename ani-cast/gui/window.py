"""
Main Application Window for AniCast GTK 4 / Libadwaita.
"""
import os
import sys
import threading
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GLib", "2.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gio", "2.0")

from gi.repository import Gtk, Adw, GLib, Gdk, Gio, Pango

# Add parent lib to sys.path for anicast_engine
LIB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "lib"))
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

import anicast_engine
from image_cache import load_texture_async
from device_manager import DeviceManager
from playback_manager import PlaybackManager
from download_manager import DownloadManager, BASE_ANIME_DIR


def clear_container(container):
    """Safely removes all child widgets from a Gtk container."""
    child = container.get_first_child()
    while child:
        nxt = child.get_next_sibling()
        container.remove(child)
        child = nxt


class AniCastWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("AniCast")
        self.set_default_size(980, 680)

        # Managers
        self.device_mgr = DeviceManager(on_update_callback=self._on_devices_updated)
        self.playback_mgr = PlaybackManager(
            on_status_change=self._on_playback_status_change,
            on_auto_advance=self._on_auto_advance,
        )
        self.download_mgr = DownloadManager()

        # State
        self.current_anime = None  # {title, slug, id, poster}
        self.current_seasons = []  # list of {title, slug, season}
        self.current_season_num = 1
        self.current_episodes = []  # list of {number, id, title}
        self.history_rows = []
        self.episode_rows = []
        self.quality = "1080p"
        self.mode = "sub"  # "sub" or "dub"

        # Toast overlay for in-app non-intrusive notifications
        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        # ToolbarView
        self.toolbar_view = Adw.ToolbarView()
        self.toast_overlay.set_child(self.toolbar_view)

        # HeaderBar setup
        self._build_header_bar()

        # View Stack setup
        self._build_view_stack()

        # Load initial continue watching and start device discovery
        self.refresh_continue_watching()
        self.device_mgr.start_discovery(timeout=3.5)

        # Handle window close to ensure subprocesses terminate
        self.connect("close-request", self._on_close_request)

    def _on_close_request(self, win):
        self.playback_mgr.stop_playback()
        return False

    def _build_header_bar(self):
        self.header = Adw.HeaderBar()
        self.toolbar_view.add_top_bar(self.header)

        # Back button
        self.back_btn = Gtk.Button(icon_name="go-previous-symbolic")
        self.back_btn.set_tooltip_text("Back")
        self.back_btn.set_visible(False)
        self.back_btn.connect("clicked", self._on_back_clicked)
        self.header.pack_start(self.back_btn)

        # Window Title
        self.title_widget = Adw.WindowTitle(title="AniCast", subtitle="Chromecast & Local Streamer")
        self.header.set_title_widget(self.title_widget)

        # Right side controls: Device Selector Popover, Quality, Mode Toggle
        # 1. Device Selector MenuButton
        self.device_btn = Gtk.MenuButton()
        self.device_btn.set_tooltip_text("Target Device")
        self.device_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.device_icon = Gtk.Image.new_from_icon_name("video-display-symbolic")
        self.device_label = Gtk.Label(label="This Device")
        self.device_btn_box.append(self.device_icon)
        self.device_btn_box.append(self.device_label)
        self.device_btn.set_child(self.device_btn_box)

        self._build_device_popover()
        self.header.pack_end(self.device_btn)

        # 2. Quality Dropdown
        self.quality_model = Gtk.StringList.new(["1080p", "720p", "360p", "best"])
        self.quality_dropdown = Gtk.DropDown.new(self.quality_model, None)
        self.quality_dropdown.set_selected(0)
        self.quality_dropdown.set_tooltip_text("Stream Quality")
        self.quality_dropdown.connect("notify::selected-item", self._on_quality_changed)
        self.header.pack_end(self.quality_dropdown)

        # 3. Audio Mode (Sub / Dub) Toggle
        self.mode_btn = Gtk.Button(label="SUB")
        self.mode_btn.add_css_class("flat")
        self.mode_btn.set_tooltip_text("Toggle Sub / Dub")
        self.mode_btn.connect("clicked", self._on_mode_toggle)
        self.header.pack_end(self.mode_btn)

        # 4. Stop Playback button (hidden when idle)
        self.stop_btn = Gtk.Button(icon_name="media-playback-stop-symbolic")
        self.stop_btn.add_css_class("destructive-action")
        self.stop_btn.set_tooltip_text("Stop Active Playback")
        self.stop_btn.set_visible(False)
        self.stop_btn.connect("clicked", lambda b: self.playback_mgr.stop_playback())
        self.header.pack_end(self.stop_btn)

    def _build_device_popover(self):
        self.device_popover = Gtk.Popover()
        pop_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        pop_box.set_margin_top(10)
        pop_box.set_margin_bottom(10)
        pop_box.set_margin_start(10)
        pop_box.set_margin_end(10)

        header_lbl = Gtk.Label(label="Select Target Device")
        header_lbl.add_css_class("heading")
        header_lbl.set_halign(Gtk.Align.START)
        pop_box.append(header_lbl)

        # List of devices
        self.device_list_box = Gtk.ListBox()
        self.device_list_box.add_css_class("boxed-list")
        self.device_list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        pop_box.append(self.device_list_box)

        # Scan button
        scan_btn = Gtk.Button(label="Scan Local Network (mDNS)")
        scan_btn.set_icon_name("view-refresh-symbolic")
        scan_btn.connect("clicked", self._on_scan_devices_clicked)
        pop_box.append(scan_btn)

        self.device_popover.set_child(pop_box)
        self.device_btn.set_popover(self.device_popover)
        self._populate_device_list()

    def _populate_device_list(self):
        clear_container(self.device_list_box)

        selected_dev = self.device_mgr.get_selected_device()
        self._update_header_device_label(selected_dev)

        for dev in self.device_mgr.devices:
            row = Adw.ActionRow()
            is_active = dev["id"] == selected_dev["id"] or dev["name"] == selected_dev["name"]
            is_local = dev.get("is_local", False)

            icon_name = "computer-symbolic" if is_local else "tv-symbolic"
            row.add_prefix(Gtk.Image.new_from_icon_name(icon_name))

            title = dev["name"]
            row.set_title(title)
            subtitle = dev.get("ip", "") if not is_local else "Direct Playback on Monitor"
            if subtitle:
                row.set_subtitle(subtitle)

            if is_active:
                check = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
                check.add_css_class("accent")
                row.add_suffix(check)

            # Click handler
            btn = Gtk.Button(icon_name="media-playback-start-symbolic" if is_active else "pan-end-symbolic")
            btn.add_css_class("flat")
            btn.connect("clicked", lambda b, d=dev: self._on_device_selected(d))
            row.add_suffix(btn)
            row.set_activatable(True)
            self._connect_row_activate(row, dev)

            self.device_list_box.append(row)

    def _connect_row_activate(self, row, dev):
        gesture = Gtk.GestureClick.new()
        gesture.connect("released", lambda g, n, x, y, d=dev: self._on_device_selected(d))
        row.add_controller(gesture)

    def _on_device_selected(self, dev):
        self.device_mgr.set_selected_device(dev["id"])
        self._populate_device_list()
        self.device_popover.popdown()
        self._update_header_device_label(dev)
        # Update hero button text
        self.refresh_continue_watching()
        self.show_toast(f"Target device: {dev['name']}")

    def _update_header_device_label(self, dev):
        is_local = dev.get("is_local", False)
        icon_name = "computer-symbolic" if is_local else "tv-symbolic"
        self.device_icon.set_from_icon_name(icon_name)
        short_name = dev["name"]
        if is_local:
            short_name = "This Device (Local)"
        elif len(short_name) > 18:
            short_name = short_name[:16] + "..."
        self.device_label.set_label(short_name)

    def _on_scan_devices_clicked(self, btn):
        btn.set_sensitive(False)
        self.show_toast("Scanning local network for Cast devices...")
        self.device_mgr.start_discovery(timeout=3.0)
        GLib.timeout_add(3200, lambda: btn.set_sensitive(True))

    def _on_devices_updated(self, devices):
        self._populate_device_list()
        self.refresh_continue_watching()

    def _on_quality_changed(self, dropdown, _pspec):
        item = dropdown.get_selected_item()
        if item:
            self.quality = item.get_string()

    def _on_mode_toggle(self, btn):
        if self.mode == "sub":
            self.mode = "dub"
            self.mode_btn.set_label("DUB")
            self.show_toast("Audio mode: English Dub")
        else:
            self.mode = "sub"
            self.mode_btn.set_label("SUB")
            self.show_toast("Audio mode: Japanese Subtitles")

    def _build_view_stack(self):
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(200)
        self.toolbar_view.set_content(self.stack)

        # 1. Home Page
        self.home_page = self._create_home_page()
        self.stack.add_named(self.home_page, "home")

        # 2. Search Page
        self.search_page = self._create_search_page()
        self.stack.add_named(self.search_page, "search")

        # 3. Episodes Page
        self.episodes_page = self._create_episodes_page()
        self.stack.add_named(self.episodes_page, "episodes")

        self.stack.set_visible_child_name("home")

    def _create_home_page(self):
        clamp = Adw.Clamp()
        clamp.set_maximum_size(780)
        clamp.set_tightening_threshold(600)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        box.set_margin_top(20)
        box.set_margin_bottom(24)
        box.set_margin_start(16)
        box.set_margin_end(16)

        # Search Entry Bar
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search anime (e.g. Solo Leveling, Bleach, Jujutsu Kaisen)...")
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("activate", self._on_search_activated)
        box.append(self.search_entry)

        # Hero Card: "Continue Watching"
        self.hero_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(self.hero_container)

        # Recent Watch History Group
        self.history_group = Adw.PreferencesGroup()
        self.history_group.set_title("Recent Watch History")
        box.append(self.history_group)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_propagate_natural_height(True)
        scrolled.set_child(box)
        clamp.set_child(scrolled)
        return clamp

    def refresh_continue_watching(self):
        clear_container(self.hero_container)

        target = anicast_engine.resolve_continue_target()
        if not target:
            # Welcoming banner
            banner = Adw.Bin()
            banner.add_css_class("card")
            b_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            b_box.set_margin_top(24)
            b_box.set_margin_bottom(24)
            b_box.set_margin_start(20)
            b_box.set_margin_end(20)

            lbl = Gtk.Label(label="Welcome to AniCast!")
            lbl.add_css_class("hero-title")
            b_box.append(lbl)
            sub = Gtk.Label(label="Search for an anime above to start streaming directly to your TV or local screen.")
            sub.set_wrap(True)
            b_box.append(sub)
            banner.set_child(b_box)
            self.hero_container.append(banner)
            self._populate_recent_history()
            return

        # Build prominent Continue Watching Hero Card
        hero_card = Adw.Bin()
        hero_card.add_css_class("card")
        hero_card.add_css_class("hero-card")

        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        main_box.set_margin_top(16)
        main_box.set_margin_bottom(16)
        main_box.set_margin_start(16)
        main_box.set_margin_end(16)

        # Poster image (left side)
        poster_frame = Gtk.Frame()
        poster_frame.add_css_class("poster-frame")
        self.hero_poster = Gtk.Picture()
        self.hero_poster.set_size_request(90, 130)
        self.hero_poster.set_content_fit(Gtk.ContentFit.COVER)
        self.hero_poster.add_css_class("poster-img")
        poster_frame.set_child(self.hero_poster)
        main_box.append(poster_frame)

        # Info Box (right side)
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        info_box.set_hexpand(True)

        header_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        c_badge = Gtk.Label(label="CONTINUE WATCHING")
        c_badge.add_css_class("badge-progress")
        header_row.append(c_badge)
        info_box.append(header_row)

        title_lbl = Gtk.Label(label=target["anime_base"])
        title_lbl.add_css_class("hero-title")
        title_lbl.set_halign(Gtk.Align.START)
        title_lbl.set_wrap(True)
        title_lbl.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        info_box.append(title_lbl)

        sub_lbl = Gtk.Label(label=f"Season {target['season']} • Episode {target['episode']}")
        sub_lbl.add_css_class("hero-subtitle")
        sub_lbl.set_halign(Gtk.Align.START)
        info_box.append(sub_lbl)

        # Timestamp / status text
        if target["was_completed"]:
            time_txt = "Next Episode"
        elif target["timestamp"] > 0:
            time_txt = f"Resuming at {target['time_str']}"
        else:
            time_txt = "Starting at 00:00"

        time_lbl = Gtk.Label(label=time_txt)
        time_lbl.add_css_class("hero-time")
        time_lbl.set_halign(Gtk.Align.START)
        info_box.append(time_lbl)

        # Action Button: 1-click Continue Watching
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_box.set_margin_top(8)

        dev = self.device_mgr.get_selected_device()
        dev_short = dev["name"] if dev else "This Device"
        if len(dev_short) > 20:
            dev_short = dev_short[:18] + "..."

        continue_btn = Gtk.Button()
        continue_btn.add_css_class("suggested-action")
        continue_btn.add_css_class("pill")
        c_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        c_content.set_margin_start(16)
        c_content.set_margin_end(16)
        c_content.set_margin_top(8)
        c_content.set_margin_bottom(8)
        c_content.append(Gtk.Image.new_from_icon_name("media-playback-start-symbolic"))
        c_content.append(Gtk.Label(label=f"Continue on {dev_short}"))
        continue_btn.set_child(c_content)
        continue_btn.connect("clicked", lambda b, t=target: self._on_continue_clicked(t))
        btn_box.append(continue_btn)

        # Browse episodes button
        browse_btn = Gtk.Button(label="View Episodes")
        browse_btn.add_css_class("flat")
        browse_btn.add_css_class("pill")
        browse_btn.connect("clicked", lambda b, t=target: self._on_browse_target_clicked(t))
        btn_box.append(browse_btn)

        info_box.append(btn_box)
        main_box.append(info_box)
        hero_card.set_child(main_box)
        self.hero_container.append(hero_card)

        # Asynchronously fetch poster for hero card
        self._load_hero_poster_async(target["search_title"])
        self._populate_recent_history()

    def _load_hero_poster_async(self, search_title):
        def _fetch():
            try:
                results = anicast_engine.search_anime(search_title)
                if results and results[0].get("poster"):
                    poster_url = results[0]["poster"]
                    load_texture_async(poster_url, lambda tex: self.hero_poster.set_paintable(tex))
            except Exception:
                pass

        threading.Thread(target=_fetch, daemon=True).start()

    def _populate_recent_history(self):
        for r in self.history_rows:
            try:
                self.history_group.remove(r)
            except Exception:
                pass
        self.history_rows.clear()

        data = anicast_engine.load_resume_state()
        if not data:
            self.history_group.set_visible(False)
            return

        sorted_items = sorted(data.values(), key=lambda x: x.get("updated_at", 0), reverse=True)
        # Exclude currently watched hero entry if already top, or show top 6
        items_to_show = sorted_items[1:7] if len(sorted_items) > 1 else sorted_items[:5]
        if not items_to_show:
            self.history_group.set_visible(False)
            return

        self.history_group.set_visible(True)
        for item in items_to_show:
            title = item.get("title", "")
            pos = float(item.get("position", 0.0))
            dur = float(item.get("duration", 0.0))
            fin = item.get("finished", False)

            anime_base, season, ep = anicast_engine.parse_anime_title(title)
            row = Adw.ActionRow()
            row.set_title(anime_base)
            row.set_subtitle(f"Season {season} Episode {ep}")

            # Badge / status
            if fin:
                badge = Gtk.Label(label="Completed ✓")
                badge.add_css_class("badge-watched")
            elif pos > 0:
                mins = int(pos // 60)
                secs = int(pos % 60)
                badge = Gtk.Label(label=f"Paused at {mins:02d}:{secs:02d}")
                badge.add_css_class("badge-progress")
            else:
                badge = Gtk.Label(label="Not Started")

            row.add_suffix(badge)

            # Quick play button
            play_btn = Gtk.Button(icon_name="media-playback-start-symbolic")
            play_btn.add_css_class("flat")
            play_btn.set_tooltip_text("Play this episode")
            play_btn.connect("clicked", lambda b, it=item: self._on_history_item_clicked(it))
            row.add_suffix(play_btn)

            row.set_activatable(True)
            self._connect_history_row(row, item)
            self.history_group.add(row)
            self.history_rows.append(row)

    def _connect_history_row(self, row, item):
        gesture = Gtk.GestureClick.new()
        gesture.connect("released", lambda g, n, x, y, it=item: self._on_history_item_clicked(it))
        row.add_controller(gesture)

    def _on_history_item_clicked(self, item):
        title = item.get("title", "")
        anime_base, season, ep = anicast_engine.parse_anime_title(title)
        pos = float(item.get("position", 0.0))
        search_q = f"{anime_base} Season {season}" if season > 1 else anime_base

        self.show_toast(f"Loading {anime_base} Season {season} Ep {ep}...")

        def _worker():
            results = anicast_engine.search_anime(search_q)
            if not results:
                results = anicast_engine.search_anime(anime_base)
            if results:
                target = results[0]
                eps = anicast_engine.get_episodes(target["slug"])
                target_ep_obj = next((e for e in eps if int(float(e["number"])) == ep), eps[0] if eps else None)
                if target_ep_obj:
                    dev = self.device_mgr.get_selected_device()
                    self.playback_mgr.play_episode(
                        anime_base,
                        season,
                        ep,
                        target_ep_obj["id"],
                        eps,
                        dev,
                        mode=self.mode,
                        quality=self.quality,
                        explicit_start_time=pos if pos > 5.0 else None,
                    )

        threading.Thread(target=_worker, daemon=True).start()

    def _on_continue_clicked(self, target):
        dev = self.device_mgr.get_selected_device()
        self.show_toast(f"Starting {target['anime_base']} on {dev['name']}...")

        def _worker():
            results = anicast_engine.search_anime(target["search_title"])
            if not results:
                results = anicast_engine.search_anime(target["anime_base"])
            if results:
                anime = results[0]
                eps = anicast_engine.get_episodes(anime["slug"])
                target_ep_obj = next((e for e in eps if int(float(e["number"])) == target["episode"]), eps[0] if eps else None)
                if target_ep_obj:
                    self.playback_mgr.play_episode(
                        target["anime_base"],
                        target["season"],
                        target["episode"],
                        target_ep_obj["id"],
                        eps,
                        dev,
                        mode=self.mode,
                        quality=self.quality,
                        explicit_start_time=target["timestamp"],
                    )

        threading.Thread(target=_worker, daemon=True).start()

    def _on_browse_target_clicked(self, target):
        def _worker():
            results = anicast_engine.search_anime(target["search_title"])
            if not results:
                results = anicast_engine.search_anime(target["anime_base"])
            if results:
                GLib.idle_add(self._load_anime_details, results[0])

        threading.Thread(target=_worker, daemon=True).start()

    # Search Page Setup
    def _create_search_page(self):
        scrolled = Gtk.ScrolledWindow()
        clamp = Adw.Clamp()
        clamp.set_maximum_size(920)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.set_margin_top(16)
        box.set_margin_bottom(24)
        box.set_margin_start(16)
        box.set_margin_end(16)

        self.search_header_lbl = Gtk.Label(label="Search Results")
        self.search_header_lbl.add_css_class("title-2")
        self.search_header_lbl.set_halign(Gtk.Align.START)
        box.append(self.search_header_lbl)

        # Flowbox / Grid for cards
        self.results_flowbox = Gtk.FlowBox()
        self.results_flowbox.set_valign(Gtk.Align.START)
        self.results_flowbox.set_max_children_per_line(4)
        self.results_flowbox.set_min_children_per_line(2)
        self.results_flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.results_flowbox.set_column_spacing(16)
        self.results_flowbox.set_row_spacing(16)
        box.append(self.results_flowbox)

        clamp.set_child(box)
        scrolled.set_child(clamp)
        return scrolled

    def _on_search_activated(self, entry):
        q = entry.get_text().strip()
        if not q:
            return

        self.search_header_lbl.set_label(f"Searching for '{q}'...")
        self.stack.set_visible_child_name("search")
        self.back_btn.set_visible(True)

        # Clear existing results
        clear_container(self.results_flowbox)

        spinner = Gtk.Spinner()
        spinner.set_size_request(48, 48)
        spinner.start()
        self.results_flowbox.append(spinner)

        def _worker():
            results = anicast_engine.search_anime(q)
            GLib.idle_add(self._display_search_results, q, results)

        threading.Thread(target=_worker, daemon=True).start()

    def _display_search_results(self, query, results):
        # Clear spinner
        clear_container(self.results_flowbox)

        self.search_header_lbl.set_label(f"Results for '{query}' ({len(results)} found)")

        if not results:
            no_lbl = Gtk.Label(label="No anime found matching your query. Try another search!")
            no_lbl.set_margin_top(40)
            self.results_flowbox.append(no_lbl)
            return

        for anime in results:
            card = self._create_anime_card(anime)
            self.results_flowbox.append(card)

    def _create_anime_card(self, anime):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.set_size_request(180, 290)
        card.add_css_class("card")
        card.set_margin_top(4)
        card.set_margin_bottom(4)
        card.set_margin_start(4)
        card.set_margin_end(4)

        # Poster Image
        pic = Gtk.Picture()
        pic.set_size_request(170, 230)
        pic.set_content_fit(Gtk.ContentFit.COVER)
        pic.add_css_class("poster-img")
        card.append(pic)

        if anime.get("poster"):
            load_texture_async(anime["poster"], lambda tex: pic.set_paintable(tex))
        else:
            pic.set_paintable(None)

        # Title Label
        title_lbl = Gtk.Label(label=anime["title"])
        title_lbl.set_halign(Gtk.Align.CENTER)
        title_lbl.set_wrap(True)
        title_lbl.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        title_lbl.set_lines(2)
        title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        title_lbl.add_css_class("heading")
        card.append(title_lbl)

        # Click gesture to load episodes
        gesture = Gtk.GestureClick.new()
        gesture.connect("released", lambda g, n, x, y, a=anime: self._load_anime_details(a))
        card.add_controller(gesture)

        return card

    # Episodes Page Setup
    def _create_episodes_page(self):
        scrolled = Gtk.ScrolledWindow()
        clamp = Adw.Clamp()
        clamp.set_maximum_size(860)

        self.ep_content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.ep_content_box.set_margin_top(16)
        self.ep_content_box.set_margin_bottom(24)
        self.ep_content_box.set_margin_start(16)
        self.ep_content_box.set_margin_end(16)

        # Header area: Poster, Title, Actions
        self.ep_header_card = Adw.Bin()
        self.ep_header_card.add_css_class("card")
        self.ep_content_box.append(self.ep_header_card)

        # Season selector row
        self.season_selector_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.ep_content_box.append(self.season_selector_box)

        # Live Season Download Banner (visible only while downloading)
        self.download_banner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.download_banner.add_css_class("download-banner")
        self.download_banner.set_visible(False)

        d_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.download_status_lbl = Gtk.Label(label="Downloading Season...")
        self.download_status_lbl.set_halign(Gtk.Align.START)
        self.download_status_lbl.set_hexpand(True)
        d_row.append(self.download_status_lbl)

        self.download_cancel_btn = Gtk.Button(label="Cancel")
        self.download_cancel_btn.add_css_class("destructive-action")
        self.download_cancel_btn.connect("clicked", lambda b: self.download_mgr.cancel())
        d_row.append(self.download_cancel_btn)
        self.download_banner.append(d_row)

        self.download_progress = Gtk.ProgressBar()
        self.download_progress.set_show_text(True)
        self.download_banner.append(self.download_progress)
        self.ep_content_box.append(self.download_banner)

        # Episode list group
        self.episodes_group = Adw.PreferencesGroup()
        self.episodes_group.set_title("Episodes")
        self.ep_content_box.append(self.episodes_group)

        clamp.set_child(self.ep_content_box)
        scrolled.set_child(clamp)
        return scrolled

    def _load_anime_details(self, anime):
        self.current_anime = anime
        self.title_widget.set_subtitle(anime["title"])
        self.back_btn.set_visible(True)
        self.stack.set_visible_child_name("episodes")

        # Set up header card
        h_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        h_box.set_margin_top(16)
        h_box.set_margin_bottom(16)
        h_box.set_margin_start(16)
        h_box.set_margin_end(16)

        ep_poster = Gtk.Picture()
        ep_poster.set_size_request(85, 120)
        ep_poster.set_content_fit(Gtk.ContentFit.COVER)
        ep_poster.add_css_class("poster-img")
        h_box.append(ep_poster)

        if anime.get("poster"):
            load_texture_async(anime["poster"], lambda tex: ep_poster.set_paintable(tex))

        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        right_box.set_hexpand(True)

        a_title = Gtk.Label(label=anime["title"])
        a_title.add_css_class("title-2")
        a_title.set_halign(Gtk.Align.START)
        a_title.set_wrap(True)
        right_box.append(a_title)

        # Action Buttons: Play Season, Download Season
        actions_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        play_season_btn = Gtk.Button()
        play_season_btn.add_css_class("suggested-action")
        play_season_btn.add_css_class("pill")
        ps_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        ps_box.append(Gtk.Image.new_from_icon_name("media-playback-start-symbolic"))
        ps_box.append(Gtk.Label(label="Play Season"))
        play_season_btn.set_child(ps_box)
        play_season_btn.connect("clicked", self._on_play_season_clicked)
        actions_row.append(play_season_btn)

        # Download Season Button (Requirement 4)
        dl_season_btn = Gtk.Button()
        dl_season_btn.add_css_class("pill")
        dl_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        dl_box.append(Gtk.Image.new_from_icon_name("folder-download-symbolic"))
        dl_box.append(Gtk.Label(label="Download Season"))
        dl_season_btn.set_child(dl_box)
        dl_season_btn.connect("clicked", self._on_download_season_clicked)
        actions_row.append(dl_season_btn)

        right_box.append(actions_row)
        h_box.append(right_box)
        self.ep_header_card.set_child(h_box)

        # Fetch episodes & related seasons in background
        def _fetch():
            eps = anicast_engine.get_episodes(anime["slug"])
            seasons = anicast_engine.get_related_seasons(anime["slug"])
            _, s_num, _ = anicast_engine.parse_anime_title(anime["title"])
            GLib.idle_add(self._display_episodes_and_seasons, eps, seasons, s_num)

        threading.Thread(target=_fetch, daemon=True).start()

    def _display_episodes_and_seasons(self, episodes, seasons, current_season_num):
        self.current_episodes = episodes
        self.current_seasons = seasons
        self.current_season_num = current_season_num

        # 1. Update season selector buttons if multiple seasons exist
        clear_container(self.season_selector_box)

        if seasons and len(seasons) > 1:
            lbl = Gtk.Label(label="Seasons:")
            lbl.add_css_class("heading")
            self.season_selector_box.append(lbl)

            for s in seasons:
                s_btn = Gtk.Button(label=f"Season {s['season']}")
                if s["season"] == current_season_num:
                    s_btn.add_css_class("suggested-action")
                s_btn.connect("clicked", lambda b, s_info=s: self._on_season_tab_clicked(s_info))
                self.season_selector_box.append(s_btn)

        # 2. Populate episodes list
        for r in self.episode_rows:
            try:
                self.episodes_group.remove(r)
            except Exception:
                pass
        self.episode_rows.clear()

        self.episodes_group.set_title(f"Season {current_season_num} Episodes ({len(episodes)} total)")

        resume_data = anicast_engine.load_resume_state()
        base_anime, _, _ = anicast_engine.parse_anime_title(self.current_anime["title"])

        for ep in episodes:
            row = Adw.ActionRow()
            ep_num = ep["number"]
            row.set_title(f"Episode {ep_num}")

            full_title = (
                f"{base_anime} Season {current_season_num} Episode {ep_num}"
                if current_season_num > 1
                else f"{base_anime} Episode {ep_num}"
            )

            # Check resume state
            res_item = next((v for k, v in resume_data.items() if k.strip().lower() == full_title.strip().lower()), None)
            if res_item:
                if res_item.get("finished"):
                    b = Gtk.Label(label="Watched ✓")
                    b.add_css_class("badge-watched")
                    row.add_suffix(b)
                elif float(res_item.get("position", 0.0)) > 5.0:
                    mins = int(float(res_item["position"]) // 60)
                    secs = int(float(res_item["position"]) % 60)
                    b = Gtk.Label(label=f"Paused {mins:02d}:{secs:02d}")
                    b.add_css_class("badge-progress")
                    row.add_suffix(b)

            # Check if file exists on disk
            try:
                ep_int = int(float(ep_num))
                fname = f"{base_anime} - Episode {ep_int:02d}.mp4"
            except Exception:
                fname = f"{base_anime} - Episode {ep_num}.mp4"
            season_dir = f"{base_anime} Season {current_season_num}" if current_season_num > 1 else base_anime
            dest_dir = os.path.join(BASE_ANIME_DIR, season_dir)
            local_path = os.path.join(dest_dir, fname)
            if not os.path.exists(local_path):
                local_path = os.path.join(BASE_ANIME_DIR, base_anime, fname)
            if os.path.exists(local_path) and os.path.getsize(local_path) > 5 * 1024 * 1024:
                dl_badge = Gtk.Label(label="Downloaded ✓")
                dl_badge.add_css_class("badge-watched")
                row.add_suffix(dl_badge)

            # Play Button
            p_btn = Gtk.Button(icon_name="media-playback-start-symbolic")
            p_btn.add_css_class("flat")
            p_btn.set_tooltip_text("Play Episode")
            p_btn.connect("clicked", lambda b, ep_obj=ep: self._on_play_episode_clicked(ep_obj))
            row.add_suffix(p_btn)

            row.set_activatable(True)
            self._connect_ep_row(row, ep)
            self.episodes_group.add(row)
            self.episode_rows.append(row)

    def _connect_ep_row(self, row, ep):
        gesture = Gtk.GestureClick.new()
        gesture.connect("released", lambda g, n, x, y, e=ep: self._on_play_episode_clicked(e))
        row.add_controller(gesture)

    def _on_season_tab_clicked(self, season_info):
        self.show_toast(f"Loading Season {season_info['season']}...")
        self.current_anime = {
            "title": season_info["title"],
            "slug": season_info["slug"],
            "id": season_info["slug"].split("-")[-1],
            "poster": self.current_anime.get("poster"),
        }
        self.title_widget.set_subtitle(season_info["title"])

        def _fetch():
            eps = anicast_engine.get_episodes(season_info["slug"])
            GLib.idle_add(self._display_episodes_and_seasons, eps, self.current_seasons, season_info["season"])

        threading.Thread(target=_fetch, daemon=True).start()

    def _on_play_episode_clicked(self, ep_obj):
        dev = self.device_mgr.get_selected_device()
        try:
            ep_int = int(float(ep_obj["number"]))
        except Exception:
            ep_int = 1

        base_title, _, _ = anicast_engine.parse_anime_title(self.current_anime["title"])

        self.playback_mgr.play_episode(
            base_title,
            self.current_season_num,
            ep_int,
            ep_obj["id"],
            self.current_episodes,
            dev,
            mode=self.mode,
            quality=self.quality,
        )

    def _on_play_season_clicked(self, btn):
        if self.current_episodes:
            self._on_play_episode_clicked(self.current_episodes[0])

    def _on_download_season_clicked(self, btn):
        if self.download_mgr.is_downloading:
            self.show_toast("A download is already running!")
            return

        self.download_banner.set_visible(True)
        self.download_progress.set_fraction(0.0)
        self.download_status_lbl.set_label("Preparing season download (scanning completed episodes)...")

        ok = self.download_mgr.start_season_download(
            self.current_anime["title"],
            self.current_season_num,
            self.current_episodes,
            quality=self.quality,
            mode=self.mode,
            on_progress=self._on_download_progress,
            on_finished=self._on_download_finished,
        )
        if not ok:
            self.show_toast("Failed to start season download.")

    def _on_download_progress(self, info):
        self.download_banner.set_visible(True)
        msg = info.get("message", "")
        pct = info.get("percent", 0.0)
        self.download_status_lbl.set_label(msg)
        self.download_progress.set_fraction(pct)

    def _on_download_finished(self, summary):
        self.download_banner.set_visible(False)
        msg = summary.get("message", "Season download finished.")
        self.show_toast(msg)
        # Refresh episodes view so newly downloaded files display badge
        if self.current_episodes:
            self._display_episodes_and_seasons(self.current_episodes, self.current_seasons, self.current_season_num)

    def _on_back_clicked(self, btn):
        current_child = self.stack.get_visible_child_name()
        if current_child == "episodes":
            self.stack.set_visible_child_name("search" if self.search_entry.get_text() else "home")
            if self.stack.get_visible_child_name() == "home":
                self.back_btn.set_visible(False)
                self.title_widget.set_subtitle("Chromecast & Local Streamer")
                self.refresh_continue_watching()
        elif current_child == "search":
            self.stack.set_visible_child_name("home")
            self.back_btn.set_visible(False)
            self.title_widget.set_subtitle("Chromecast & Local Streamer")
            self.refresh_continue_watching()

    # Playback Callbacks
    def _on_playback_status_change(self, status, detail):
        if status == "playing":
            self.stop_btn.set_visible(True)
            self.show_toast(f"Playing {detail}")
        elif status == "loading":
            self.show_toast(f"Loading stream: {detail}...")
        elif status == "stopped":
            self.stop_btn.set_visible(False)
            self.refresh_continue_watching()
            if self.stack.get_visible_child_name() == "episodes" and self.current_episodes:
                self._display_episodes_and_seasons(self.current_episodes, self.current_seasons, self.current_season_num)
        elif status == "error":
            self.stop_btn.set_visible(False)
            self.show_toast(f"Playback error: {detail}")

    def _on_auto_advance(self, anime_title, season_num, episode_num, _ep_id):
        self.show_toast(f"Auto-advancing: Season {season_num} Episode {episode_num}")
        self.refresh_continue_watching()
        if self.stack.get_visible_child_name() == "episodes" and self.current_episodes:
            self._display_episodes_and_seasons(self.current_episodes, self.current_seasons, self.current_season_num)

    def show_toast(self, text):
        toast = Adw.Toast.new(text)
        toast.set_timeout(3)
        self.toast_overlay.add_toast(toast)
