"""
Main Application Window for OmniView GTK 4 / Libadwaita Media Suite.
Multi-tab layout supporting:
  - 🌸 Anime
  - 🎬 Movies & TV Shows
  - 💾 Downloads / Library
Local MPV Playback & Chromecast TV Casting across all media types.
"""
import os
import sys
import threading
import subprocess
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GLib", "2.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gio", "2.0")

from gi.repository import Gtk, Adw, GLib, Gdk, Gio, Pango

# Add parent lib to sys.path
LIB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "lib"))
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

import anicast_engine
import movies_engine
from image_cache import load_texture_async
from device_manager import DeviceManager
from playback_manager import PlaybackManager
from download_manager import DownloadManager, scan_local_library, BASE_ANIME_DIR, BASE_MOVIES_DIR


def clear_container(container):
    """Safely removes all child widgets from a Gtk container."""
    child = container.get_first_child()
    while child:
        nxt = child.get_next_sibling()
        container.remove(child)
        child = nxt


class OmniViewWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("OmniView")
        self.set_default_size(1020, 660)
        self.set_size_request(600, 460)

        # Managers
        self.device_mgr = DeviceManager(on_update_callback=self._on_devices_updated)
        self.playback_mgr = PlaybackManager(
            on_status_change=self._on_playback_status_change,
            on_auto_advance=self._on_auto_advance,
        )
        self.download_mgr = DownloadManager()

        # State - Anime
        self.current_anime = None
        self.current_seasons = []
        self.current_season_num = 1
        self.current_episodes = []
        self.history_rows = []
        self.episode_rows = []

        # State - Movies & Shows
        self.current_movie_item = None
        self.movie_seasons_dict = {}
        self.current_movie_season_num = 1
        self.tv_episode_rows = []
        self.library_rows = []

        # Global stream preferences
        self.quality = "1080p"
        self.mode = "sub"

        # Toast overlay
        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        # ToolbarView
        self.toolbar_view = Adw.ToolbarView()
        self.toast_overlay.set_child(self.toolbar_view)

        # Build ViewStack first so HeaderBar switcher can bind to it
        self._build_main_view_stack()

        # Build HeaderBar
        self._build_header_bar()

        # Initial data loading
        self.refresh_anime_continue_watching()
        self.refresh_local_library()
        self.device_mgr.start_discovery(timeout=3.5)

        # Terminate processes on window close
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

        # OmniView HeaderBar Brand Title Widget (Left side next to Back button)
        self.brand_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.brand_box.add_css_class("omniview-brand")
        self.brand_box.set_valign(Gtk.Align.CENTER)

        self.brand_icon = Gtk.Image.new_from_icon_name("video-display-symbolic")
        self.brand_icon.add_css_class("omniview-brand-icon")

        self.brand_label = Gtk.Label(label="OmniView")
        self.brand_label.add_css_class("heading")
        self.brand_label.add_css_class("omniview-brand-label")

        self.brand_box.append(self.brand_icon)
        self.brand_box.append(self.brand_label)
        self.header.pack_start(self.brand_box)

        # Centered Multi-Tab ViewSwitcher
        self.view_switcher = Adw.ViewSwitcher()
        self.view_switcher.set_stack(self.main_view_stack)
        self.view_switcher.set_policy(Adw.ViewSwitcherPolicy.WIDE)
        self.header.set_title_widget(self.view_switcher)

        # Right side controls: Device Selector, Quality, Audio Mode, Stop
        # 1. Device Selector MenuButton
        self.device_btn = Gtk.MenuButton()
        self.device_btn.set_tooltip_text("Target Device (Local MPV or Chromecast TV)")
        self.device_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.device_icon = Gtk.Image.new_from_icon_name("computer-symbolic")
        self.device_label = Gtk.Label(label="This Device")
        self.device_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.device_label.set_max_width_chars(15)
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
        pop_box.set_margin_top(8)
        pop_box.set_margin_bottom(8)
        pop_box.set_margin_start(8)
        pop_box.set_margin_end(8)
        pop_box.set_size_request(270, -1)

        header_lbl = Gtk.Label(label="Select Playback Target")
        header_lbl.add_css_class("heading")
        header_lbl.set_halign(Gtk.Align.START)
        pop_box.append(header_lbl)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_max_content_height(240)
        scrolled.set_propagate_natural_height(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.device_list_box = Gtk.ListBox()
        self.device_list_box.add_css_class("boxed-list")
        self.device_list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        scrolled.set_child(self.device_list_box)
        pop_box.append(scrolled)

        scan_btn = Gtk.Button(label="Scan Network Chromecasts")
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

            title = "This Device (Local Screen / MPV)" if is_local else dev["name"]
            row.set_title(title)
            subtitle = "Direct Local Playback (Default)" if is_local else (dev.get("ip", "") or "Google Cast")
            if subtitle:
                row.set_subtitle(subtitle)

            if is_active:
                check = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
                check.add_css_class("accent")
                row.add_suffix(check)

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
        self.refresh_anime_continue_watching()
        self.show_toast(f"Target device: {dev['name']}")

    def _update_header_device_label(self, dev):
        is_local = dev.get("is_local", False)
        icon_name = "computer-symbolic" if is_local else "tv-symbolic"
        self.device_icon.set_from_icon_name(icon_name)
        if is_local:
            short_name = "This Device"
        else:
            short_name = dev.get("name", "TV")
            if len(short_name) > 16:
                short_name = short_name[:14] + "..."
        self.device_label.set_label(short_name)

    def _on_scan_devices_clicked(self, btn):
        btn.set_sensitive(False)
        self.show_toast("Scanning local network for Cast devices...")
        self.device_mgr.start_discovery(timeout=3.0)
        GLib.timeout_add(3200, lambda: btn.set_sensitive(True))

    def _on_devices_updated(self, devices):
        self._populate_device_list()
        self.refresh_anime_continue_watching()

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

    # =========================================================================
    # Multi-Tab Main ViewStack
    # =========================================================================
    def _build_main_view_stack(self):
        self.main_view_stack = Adw.ViewStack()
        self.toolbar_view.set_content(self.main_view_stack)

        # Tab 1: Anime Tab Container
        self.anime_tab = self._create_anime_tab()
        p1 = self.main_view_stack.add_titled(self.anime_tab, "anime", "🌸 Anime")
        p1.set_icon_name("media-playback-start-symbolic")

        # Tab 2: Movies & TV Shows Tab Container
        self.movies_tab = self._create_movies_tab()
        p2 = self.main_view_stack.add_titled(self.movies_tab, "movies", "🎬 Movies & Shows")
        p2.set_icon_name("video-x-generic-symbolic")

        # Tab 3: Downloads & Local Library Container
        self.library_tab = self._create_library_tab()
        p3 = self.main_view_stack.add_titled(self.library_tab, "library", "💾 Downloads / Library")
        p3.set_icon_name("folder-download-symbolic")

        self.main_view_stack.connect("notify::visible-child-name", self._on_tab_switched)

    def _on_tab_switched(self, stack, _pspec):
        tab_name = stack.get_visible_child_name()
        if tab_name == "library":
            self.refresh_local_library()
        self.back_btn.set_visible(False)

    # =========================================================================
    # TAB 1: 🌸 ANIME
    # =========================================================================
    def _create_anime_tab(self):
        self.anime_substack = Gtk.Stack()
        self.anime_substack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.anime_substack.set_transition_duration(180)

        # Sub-pages: Home, Search, Episodes
        self.anime_home_page = self._create_anime_home_page()
        self.anime_substack.add_named(self.anime_home_page, "anime_home")

        self.anime_search_page = self._create_anime_search_page()
        self.anime_substack.add_named(self.anime_search_page, "anime_search")

        self.anime_episodes_page = self._create_anime_episodes_page()
        self.anime_substack.add_named(self.anime_episodes_page, "anime_episodes")

        self.anime_substack.set_visible_child_name("anime_home")
        return self.anime_substack

    def _create_anime_home_page(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(860)
        clamp.set_tightening_threshold(620)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.set_margin_top(14)
        box.set_margin_bottom(20)
        box.set_margin_start(16)
        box.set_margin_end(16)

        # Anime Search Bar
        self.anime_search_entry = Gtk.SearchEntry()
        self.anime_search_entry.set_placeholder_text("Search anime (e.g. Solo Leveling, Bleach, Jujutsu Kaisen)...")
        self.anime_search_entry.set_hexpand(True)
        self.anime_search_entry.connect("activate", self._on_anime_search_activated)
        box.append(self.anime_search_entry)

        # Hero Card: "Continue Watching"
        self.hero_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(self.hero_container)

        # Recent Watch History Group
        self.history_group = Adw.PreferencesGroup()
        self.history_group.set_title("Recent Watch History")
        box.append(self.history_group)

        clamp.set_child(box)
        scrolled.set_child(clamp)
        return scrolled

    def refresh_anime_continue_watching(self):
        clear_container(self.hero_container)

        target = anicast_engine.resolve_continue_target()
        if not target:
            banner = Adw.Bin()
            banner.add_css_class("card")
            b_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            b_box.set_margin_top(22)
            b_box.set_margin_bottom(22)
            b_box.set_margin_start(20)
            b_box.set_margin_end(20)

            lbl = Gtk.Label(label="Welcome to OmniView Anime!")
            lbl.add_css_class("hero-title")
            b_box.append(lbl)
            sub = Gtk.Label(label="Search for an anime above to start streaming directly to your TV or local screen.")
            sub.set_wrap(True)
            b_box.append(sub)
            banner.set_child(b_box)
            self.hero_container.append(banner)
            self._populate_anime_history()
            return

        hero_card = Adw.Bin()
        hero_card.add_css_class("card")
        hero_card.add_css_class("hero-card")

        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        main_box.set_margin_top(12)
        main_box.set_margin_bottom(12)
        main_box.set_margin_start(14)
        main_box.set_margin_end(14)

        poster_frame = Gtk.Frame()
        poster_frame.add_css_class("poster-frame")
        self.hero_poster = Gtk.Picture()
        self.hero_poster.set_size_request(85, 120)
        self.hero_poster.set_content_fit(Gtk.ContentFit.COVER)
        self.hero_poster.add_css_class("poster-img")
        poster_frame.set_child(self.hero_poster)
        main_box.append(poster_frame)

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
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

        time_txt = "Next Episode" if target["was_completed"] else (f"Resuming at {target['time_str']}" if target["timestamp"] > 0 else "Starting at 00:00")
        time_lbl = Gtk.Label(label=time_txt)
        time_lbl.add_css_class("hero-time")
        time_lbl.set_halign(Gtk.Align.START)
        info_box.append(time_lbl)

        # Dual Action Buttons on Hero Card
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_box.set_margin_top(6)

        dev = self.device_mgr.get_selected_device()
        dev_short = "This Device" if (dev and dev.get("is_local")) else (dev["name"] if dev else "This Device")

        # Play Locally button
        play_btn = Gtk.Button()
        play_btn.add_css_class("suggested-action")
        play_btn.add_css_class("pill")
        p_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        p_box.set_margin_start(10)
        p_box.set_margin_end(10)
        p_box.append(Gtk.Image.new_from_icon_name("media-playback-start-symbolic"))
        p_box.append(Gtk.Label(label="Play (Local MPV)"))
        play_btn.set_child(p_box)
        play_btn.connect("clicked", lambda b, t=target: self._on_continue_clicked(t, force_local=True))
        btn_box.append(play_btn)

        # Cast to TV button
        cast_btn = Gtk.Button()
        cast_btn.add_css_class("pill")
        c_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        c_box.set_margin_start(10)
        c_box.set_margin_end(10)
        c_box.append(Gtk.Image.new_from_icon_name("tv-symbolic"))
        c_box.append(Gtk.Label(label=f"Cast to {dev_short}"))
        cast_btn.set_child(c_box)
        cast_btn.connect("clicked", lambda b, t=target: self._on_continue_clicked(t, force_local=False))
        btn_box.append(cast_btn)

        # Browse episodes button
        browse_btn = Gtk.Button(label="Episodes")
        browse_btn.add_css_class("flat")
        browse_btn.add_css_class("pill")
        browse_btn.connect("clicked", lambda b, t=target: self._on_browse_target_clicked(t))
        btn_box.append(browse_btn)

        info_box.append(btn_box)
        main_box.append(info_box)
        hero_card.set_child(main_box)
        self.hero_container.append(hero_card)

        # Load poster
        self._load_anime_hero_poster(target["search_title"])
        self._populate_anime_history()

    def _load_anime_hero_poster(self, search_title):
        def _fetch():
            try:
                results = anicast_engine.search_anime(search_title)
                if results and results[0].get("poster"):
                    load_texture_async(results[0]["poster"], lambda tex: self.hero_poster.set_paintable(tex))
            except Exception:
                pass
        threading.Thread(target=_fetch, daemon=True).start()

    def _populate_anime_history(self):
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
        items_to_show = sorted_items[1:7] if len(sorted_items) > 1 else sorted_items[:5]
        if not items_to_show:
            self.history_group.set_visible(False)
            return

        self.history_group.set_visible(True)
        for item in items_to_show:
            title = item.get("title", "")
            pos = float(item.get("position", 0.0))
            fin = item.get("finished", False)

            anime_base, season, ep = anicast_engine.parse_anime_title(title)
            row = Adw.ActionRow()
            row.set_title(anime_base)
            row.set_subtitle(f"Season {season} Episode {ep}")

            if fin:
                badge = Gtk.Label(label="Completed ✓")
                badge.add_css_class("badge-watched")
            elif pos > 0:
                mins = int(pos // 60)
                secs = int(pos % 60)
                badge = Gtk.Label(label=f"Paused {mins:02d}:{secs:02d}")
                badge.add_css_class("badge-progress")
            else:
                badge = Gtk.Label(label="Not Started")
            row.add_suffix(badge)

            # Dual quick buttons on history row
            # 1. Play Local
            p_btn = Gtk.Button(icon_name="media-playback-start-symbolic")
            p_btn.add_css_class("flat")
            p_btn.set_tooltip_text("Play Locally (MPV)")
            p_btn.connect("clicked", lambda b, it=item: self._on_history_play_clicked(it, force_local=True))
            row.add_suffix(p_btn)

            # 2. Cast
            c_btn = Gtk.Button(icon_name="tv-symbolic")
            c_btn.add_css_class("flat")
            c_btn.set_tooltip_text("Cast to TV")
            c_btn.connect("clicked", lambda b, it=item: self._on_history_play_clicked(it, force_local=False))
            row.add_suffix(c_btn)

            self.history_group.add(row)
            self.history_rows.append(row)

    def _on_history_play_clicked(self, item, force_local=True):
        title = item.get("title", "")
        anime_base, season, ep = anicast_engine.parse_anime_title(title)
        pos = float(item.get("position", 0.0))
        search_q = f"{anime_base} Season {season}" if season > 1 else anime_base

        dev = {"name": "This Device (Local Screen / MPV)", "id": "local", "ip": "127.0.0.1", "is_local": True} if force_local else self.device_mgr.get_selected_device()
        self.show_toast(f"Loading {anime_base} S{season}E{ep} on {dev['name']}...")

        def _worker():
            results = anicast_engine.search_anime(search_q)
            if not results:
                results = anicast_engine.search_anime(anime_base)
            if results:
                target = results[0]
                eps = anicast_engine.get_episodes(target["slug"])
                target_ep_obj = next((e for e in eps if int(float(e["number"])) == ep), eps[0] if eps else None)
                if target_ep_obj:
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

    def _on_continue_clicked(self, target, force_local=True):
        dev = {"name": "This Device (Local Screen / MPV)", "id": "local", "ip": "127.0.0.1", "is_local": True} if force_local else self.device_mgr.get_selected_device()
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

    # Anime Search Results Page
    def _create_anime_search_page(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(980)
        clamp.set_tightening_threshold(700)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(14)
        box.set_margin_bottom(20)
        box.set_margin_start(16)
        box.set_margin_end(16)

        self.anime_search_header = Gtk.Label(label="Anime Search Results")
        self.anime_search_header.add_css_class("title-3")
        self.anime_search_header.set_halign(Gtk.Align.START)
        box.append(self.anime_search_header)

        self.anime_results_flowbox = Gtk.FlowBox()
        self.anime_results_flowbox.set_valign(Gtk.Align.START)
        self.anime_results_flowbox.set_max_children_per_line(5)
        self.anime_results_flowbox.set_min_children_per_line(2)
        self.anime_results_flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.anime_results_flowbox.set_column_spacing(12)
        self.anime_results_flowbox.set_row_spacing(12)
        self.anime_results_flowbox.set_homogeneous(True)
        box.append(self.anime_results_flowbox)

        clamp.set_child(box)
        scrolled.set_child(clamp)
        return scrolled

    def _on_anime_search_activated(self, entry):
        q = entry.get_text().strip()
        if not q:
            return

        self.anime_search_header.set_label(f"Searching anime: '{q}'...")
        self.anime_substack.set_visible_child_name("anime_search")
        self.back_btn.set_visible(True)

        clear_container(self.anime_results_flowbox)
        spinner = Gtk.Spinner()
        spinner.set_size_request(48, 48)
        spinner.start()
        self.anime_results_flowbox.append(spinner)

        def _worker():
            results = anicast_engine.search_anime(q)
            GLib.idle_add(self._display_anime_results, q, results)

        threading.Thread(target=_worker, daemon=True).start()

    def _display_anime_results(self, query, results):
        clear_container(self.anime_results_flowbox)
        self.anime_search_header.set_label(f"Anime Results for '{query}' ({len(results)} found)")

        if not results:
            no_lbl = Gtk.Label(label="No anime found matching your query. Try another search!")
            no_lbl.set_margin_top(40)
            self.anime_results_flowbox.append(no_lbl)
            return

        for anime in results:
            card = self._create_anime_card(anime)
            self.anime_results_flowbox.append(card)

    def _create_anime_card(self, anime):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.set_size_request(160, 260)
        card.add_css_class("card")
        card.add_css_class("anime-card")

        pic = Gtk.Picture()
        pic.set_size_request(150, 205)
        pic.set_content_fit(Gtk.ContentFit.COVER)
        pic.add_css_class("poster-img")
        card.append(pic)

        if anime.get("poster"):
            load_texture_async(anime["poster"], lambda tex: pic.set_paintable(tex))

        title_lbl = Gtk.Label(label=anime["title"])
        title_lbl.set_halign(Gtk.Align.CENTER)
        title_lbl.set_wrap(True)
        title_lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        title_lbl.set_lines(2)
        title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        title_lbl.add_css_class("anime-card-title")
        card.append(title_lbl)

        gesture = Gtk.GestureClick.new()
        gesture.connect("released", lambda g, n, x, y, a=anime: self._load_anime_details(a))
        card.add_controller(gesture)
        return card

    # Anime Episodes Page
    def _create_anime_episodes_page(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(880)
        clamp.set_tightening_threshold(660)

        self.anime_ep_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.anime_ep_content.set_margin_top(14)
        self.anime_ep_content.set_margin_bottom(20)
        self.anime_ep_content.set_margin_start(16)
        self.anime_ep_content.set_margin_end(16)

        self.anime_ep_header = Adw.Bin()
        self.anime_ep_header.add_css_class("card")
        self.anime_ep_content.append(self.anime_ep_header)

        self.anime_season_scroll = Gtk.ScrolledWindow()
        self.anime_season_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.anime_season_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.anime_season_scroll.set_child(self.anime_season_box)
        self.anime_ep_content.append(self.anime_season_scroll)

        # Download banner
        self.anime_download_banner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.anime_download_banner.add_css_class("download-banner")
        self.anime_download_banner.set_visible(False)

        d_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.anime_dl_status_lbl = Gtk.Label(label="Downloading Season...")
        self.anime_dl_status_lbl.set_halign(Gtk.Align.START)
        self.anime_dl_status_lbl.set_hexpand(True)
        d_row.append(self.anime_dl_status_lbl)

        self.anime_dl_cancel_btn = Gtk.Button(label="Cancel")
        self.anime_dl_cancel_btn.add_css_class("destructive-action")
        self.anime_dl_cancel_btn.connect("clicked", lambda b: self.download_mgr.cancel())
        d_row.append(self.anime_dl_cancel_btn)
        self.anime_download_banner.append(d_row)

        self.anime_dl_progress = Gtk.ProgressBar()
        self.anime_dl_progress.set_show_text(True)
        self.anime_download_banner.append(self.anime_dl_progress)
        self.anime_ep_content.append(self.anime_download_banner)

        # Episodes list group
        self.anime_episodes_group = Adw.PreferencesGroup()
        self.anime_episodes_group.set_title("Episodes")
        self.anime_ep_content.append(self.anime_episodes_group)

        clamp.set_child(self.anime_ep_content)
        scrolled.set_child(clamp)
        return scrolled

    def _load_anime_details(self, anime):
        self.current_anime = anime
        self.back_btn.set_visible(True)
        self.anime_substack.set_visible_child_name("anime_episodes")

        h_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        h_box.set_margin_top(12)
        h_box.set_margin_bottom(12)
        h_box.set_margin_start(14)
        h_box.set_margin_end(14)

        ep_poster = Gtk.Picture()
        ep_poster.set_size_request(80, 115)
        ep_poster.set_content_fit(Gtk.ContentFit.COVER)
        ep_poster.add_css_class("poster-img")
        h_box.append(ep_poster)

        if anime.get("poster"):
            load_texture_async(anime["poster"], lambda tex: ep_poster.set_paintable(tex))

        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        right_box.set_hexpand(True)

        a_title = Gtk.Label(label=anime["title"])
        a_title.add_css_class("title-3")
        a_title.set_halign(Gtk.Align.START)
        a_title.set_wrap(True)
        a_title.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        right_box.append(a_title)

        actions_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        play_btn = Gtk.Button()
        play_btn.add_css_class("suggested-action")
        play_btn.add_css_class("pill")
        ps_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        ps_box.append(Gtk.Image.new_from_icon_name("media-playback-start-symbolic"))
        ps_box.append(Gtk.Label(label="Play Season (MPV)"))
        play_btn.set_child(ps_box)
        play_btn.connect("clicked", lambda b: self._on_play_anime_season(force_local=True))
        actions_row.append(play_btn)

        cast_btn = Gtk.Button()
        cast_btn.add_css_class("pill")
        cs_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        cs_box.append(Gtk.Image.new_from_icon_name("tv-symbolic"))
        cs_box.append(Gtk.Label(label="Cast Season (TV)"))
        cast_btn.set_child(cs_box)
        cast_btn.connect("clicked", lambda b: self._on_play_anime_season(force_local=False))
        actions_row.append(cast_btn)

        dl_btn = Gtk.Button()
        dl_btn.add_css_class("pill")
        dl_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        dl_box.append(Gtk.Image.new_from_icon_name("folder-download-symbolic"))
        dl_box.append(Gtk.Label(label="Download Season"))
        dl_btn.set_child(dl_box)
        dl_btn.connect("clicked", self._on_download_anime_season)
        actions_row.append(dl_btn)

        right_box.append(actions_row)
        h_box.append(right_box)
        self.anime_ep_header.set_child(h_box)

        def _fetch():
            eps = anicast_engine.get_episodes(anime["slug"])
            seasons = anicast_engine.get_related_seasons(anime["slug"])
            _, s_num, _ = anicast_engine.parse_anime_title(anime["title"])
            GLib.idle_add(self._display_anime_episodes, eps, seasons, s_num)

        threading.Thread(target=_fetch, daemon=True).start()

    def _display_anime_episodes(self, episodes, seasons, current_season_num):
        self.current_episodes = episodes
        self.current_seasons = seasons
        self.current_season_num = current_season_num

        clear_container(self.anime_season_box)
        if seasons and len(seasons) > 1:
            lbl = Gtk.Label(label="Seasons:")
            lbl.add_css_class("heading")
            self.anime_season_box.append(lbl)
            for s in seasons:
                s_btn = Gtk.Button(label=f"Season {s['season']}")
                if s["season"] == current_season_num:
                    s_btn.add_css_class("suggested-action")
                s_btn.connect("clicked", lambda b, s_info=s: self._on_anime_season_clicked(s_info))
                self.anime_season_box.append(s_btn)

        for r in self.episode_rows:
            try:
                self.anime_episodes_group.remove(r)
            except Exception:
                pass
        self.episode_rows.clear()

        self.anime_episodes_group.set_title(f"Season {current_season_num} Episodes ({len(episodes)} total)")
        resume_data = anicast_engine.load_resume_state()
        base_anime, _, _ = anicast_engine.parse_anime_title(self.current_anime["title"])

        for ep in episodes:
            row = Adw.ActionRow()
            ep_num = ep["number"]
            row.set_title(f"Episode {ep_num}")

            full_title = f"{base_anime} Season {current_season_num} Episode {ep_num}" if current_season_num > 1 else f"{base_anime} Episode {ep_num}"

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

            # Dual Action Buttons on each episode row: Play (MPV) & Cast (TV)
            play_btn = Gtk.Button(icon_name="media-playback-start-symbolic")
            play_btn.add_css_class("flat")
            play_btn.set_tooltip_text("Play Locally (MPV)")
            play_btn.connect("clicked", lambda b, e=ep: self._on_play_anime_episode(e, force_local=True))
            row.add_suffix(play_btn)

            cast_btn = Gtk.Button(icon_name="tv-symbolic")
            cast_btn.add_css_class("flat")
            cast_btn.set_tooltip_text("Cast to TV")
            cast_btn.connect("clicked", lambda b, e=ep: self._on_play_anime_episode(e, force_local=False))
            row.add_suffix(cast_btn)

            row.set_activatable(True)
            gesture = Gtk.GestureClick.new()
            gesture.connect("released", lambda g, n, x, y, e=ep: self._on_play_anime_episode(e, force_local=True))
            row.add_controller(gesture)

            self.anime_episodes_group.add(row)
            self.episode_rows.append(row)

    def _on_anime_season_clicked(self, season_info):
        self.show_toast(f"Loading Season {season_info['season']}...")
        self.current_anime = {
            "title": season_info["title"],
            "slug": season_info["slug"],
            "id": season_info["slug"].split("-")[-1],
            "poster": self.current_anime.get("poster"),
        }
        def _fetch():
            eps = anicast_engine.get_episodes(season_info["slug"])
            GLib.idle_add(self._display_anime_episodes, eps, self.current_seasons, season_info["season"])
        threading.Thread(target=_fetch, daemon=True).start()

    def _on_play_anime_episode(self, ep_obj, force_local=True):
        dev = {"name": "This Device (Local Screen / MPV)", "id": "local", "ip": "127.0.0.1", "is_local": True} if force_local else self.device_mgr.get_selected_device()
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

    def _on_play_anime_season(self, force_local=True):
        if self.current_episodes:
            self._on_play_anime_episode(self.current_episodes[0], force_local=force_local)

    def _on_download_anime_season(self, btn):
        if self.download_mgr.is_downloading:
            self.show_toast("A download is already running!")
            return

        self.anime_download_banner.set_visible(True)
        self.anime_dl_progress.set_fraction(0.0)
        self.anime_dl_status_lbl.set_label("Preparing season download (scanning completed episodes)...")

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
        self.anime_download_banner.set_visible(True)
        msg = info.get("message", "")
        pct = info.get("percent", 0.0)
        self.anime_dl_status_lbl.set_label(msg)
        self.anime_dl_progress.set_fraction(pct)

    def _on_download_finished(self, summary):
        self.anime_download_banner.set_visible(False)
        msg = summary.get("message", "Season download finished.")
        self.show_toast(msg)
        if self.current_episodes:
            self._display_anime_episodes(self.current_episodes, self.current_seasons, self.current_season_num)

    # =========================================================================
    # TAB 2: 🎬 MOVIES & TV SHOWS
    # =========================================================================
    def _create_movies_tab(self):
        self.movies_substack = Gtk.Stack()
        self.movies_substack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.movies_substack.set_transition_duration(180)

        # Sub-pages: Home, Search, Details/Episodes
        self.movies_home_page = self._create_movies_home_page()
        self.movies_substack.add_named(self.movies_home_page, "movies_home")

        self.movies_search_page = self._create_movies_search_page()
        self.movies_substack.add_named(self.movies_search_page, "movies_search")

        self.movies_details_page = self._create_movies_details_page()
        self.movies_substack.add_named(self.movies_details_page, "movies_details")

        self.movies_substack.set_visible_child_name("movies_home")
        return self.movies_substack

    def _create_movies_home_page(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(860)
        clamp.set_tightening_threshold(620)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(14)
        box.set_margin_bottom(20)
        box.set_margin_start(16)
        box.set_margin_end(16)

        # Movies & Shows Search Bar
        self.movies_search_entry = Gtk.SearchEntry()
        self.movies_search_entry.set_placeholder_text("Search movies & TV shows (e.g. Inception, Breaking Bad, Interstellar)...")
        self.movies_search_entry.set_hexpand(True)
        self.movies_search_entry.connect("activate", self._on_movies_search_activated)
        box.append(self.movies_search_entry)

        # Welcoming hero card
        banner = Adw.Bin()
        banner.add_css_class("card")
        banner.add_css_class("hero-card")
        b_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        b_box.set_margin_top(16)
        b_box.set_margin_bottom(16)
        b_box.set_margin_start(18)
        b_box.set_margin_end(18)

        lbl = Gtk.Label(label="🎬 Universal Movies & TV Shows Streaming")
        lbl.add_css_class("hero-title")
        b_box.append(lbl)
        sub = Gtk.Label(label="Search any mainstream Hollywood movie or TV series. Stream instantly locally with MPV or cast to TV!")
        sub.set_wrap(True)
        b_box.append(sub)
        banner.set_child(b_box)
        box.append(banner)

        # Quick Picks Group
        picks_group = Adw.PreferencesGroup()
        picks_group.set_title("Popular Recommendations")
        box.append(picks_group)

        featured = [
            {"id": "tt1375666", "title": "Inception", "year": "2010", "type": "movie"},
            {"id": "tt0816692", "title": "Interstellar", "year": "2014", "type": "movie"},
            {"id": "tt0903747", "title": "Breaking Bad", "year": "2008", "type": "tv"},
            {"id": "tt0133093", "title": "The Matrix", "year": "1999", "type": "movie"},
        ]
        for f in featured:
            row = Adw.ActionRow()
            row.set_title(f["title"])
            row.set_subtitle(f"{f['year']} • {'Movie' if f['type'] == 'movie' else 'TV Series'}")

            # Badge
            badge = Gtk.Label(label="🎬 Movie" if f["type"] == "movie" else "📺 TV Show")
            badge.add_css_class("badge-movie" if f["type"] == "movie" else "badge-tv")
            row.add_suffix(badge)

            # Play local button
            p_btn = Gtk.Button(icon_name="media-playback-start-symbolic")
            p_btn.add_css_class("flat")
            p_btn.set_tooltip_text("Play Locally (MPV)")
            p_btn.connect("clicked", lambda b, it=f: self._on_quick_pick_clicked(it, force_local=True))
            row.add_suffix(p_btn)

            # Cast button
            c_btn = Gtk.Button(icon_name="tv-symbolic")
            c_btn.add_css_class("flat")
            c_btn.set_tooltip_text("Cast to TV")
            c_btn.connect("clicked", lambda b, it=f: self._on_quick_pick_clicked(it, force_local=False))
            row.add_suffix(c_btn)

            row.set_activatable(True)
            gesture = Gtk.GestureClick.new()
            gesture.connect("released", lambda g, n, x, y, it=f: self._on_load_movie_details(it))
            row.add_controller(gesture)

            picks_group.add(row)

        clamp.set_child(box)
        scrolled.set_child(clamp)
        return scrolled

    def _on_quick_pick_clicked(self, item, force_local=True):
        dev = {"name": "This Device (Local Screen / MPV)", "id": "local", "ip": "127.0.0.1", "is_local": True} if force_local else self.device_mgr.get_selected_device()
        if item["type"] == "movie":
            self.playback_mgr.play_movie(item["id"], item["title"], target_device=dev)
        else:
            self.playback_mgr.play_tv_show(item["id"], 1, 1, item["title"], target_device=dev)

    # Movies Search Page
    def _create_movies_search_page(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(980)
        clamp.set_tightening_threshold(700)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(14)
        box.set_margin_bottom(20)
        box.set_margin_start(16)
        box.set_margin_end(16)

        self.movies_search_header = Gtk.Label(label="Movies & TV Results")
        self.movies_search_header.add_css_class("title-3")
        self.movies_search_header.set_halign(Gtk.Align.START)
        box.append(self.movies_search_header)

        self.movies_results_flowbox = Gtk.FlowBox()
        self.movies_results_flowbox.set_valign(Gtk.Align.START)
        self.movies_results_flowbox.set_max_children_per_line(5)
        self.movies_results_flowbox.set_min_children_per_line(2)
        self.movies_results_flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.movies_results_flowbox.set_column_spacing(12)
        self.movies_results_flowbox.set_row_spacing(12)
        self.movies_results_flowbox.set_homogeneous(True)
        box.append(self.movies_results_flowbox)

        clamp.set_child(box)
        scrolled.set_child(clamp)
        return scrolled

    def _on_movies_search_activated(self, entry):
        q = entry.get_text().strip()
        if not q:
            return

        self.movies_search_header.set_label(f"Searching movies & TV: '{q}'...")
        self.movies_substack.set_visible_child_name("movies_search")
        self.back_btn.set_visible(True)

        clear_container(self.movies_results_flowbox)
        spinner = Gtk.Spinner()
        spinner.set_size_request(48, 48)
        spinner.start()
        self.movies_results_flowbox.append(spinner)

        def _worker():
            results = movies_engine.search_movies_and_shows(q)
            GLib.idle_add(self._display_movies_results, q, results)

        threading.Thread(target=_worker, daemon=True).start()

    def _display_movies_results(self, query, results):
        clear_container(self.movies_results_flowbox)
        self.movies_search_header.set_label(f"Results for '{query}' ({len(results)} found)")

        if not results:
            no_lbl = Gtk.Label(label="No movies or TV shows found matching your query.")
            no_lbl.set_margin_top(40)
            self.movies_results_flowbox.append(no_lbl)
            return

        for item in results:
            card = self._create_movie_card(item)
            self.movies_results_flowbox.append(card)

    def _create_movie_card(self, item):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        card.set_size_request(165, 290)
        card.add_css_class("card")
        card.add_css_class("media-card")

        pic = Gtk.Picture()
        pic.set_size_request(150, 195)
        pic.set_content_fit(Gtk.ContentFit.COVER)
        pic.add_css_class("poster-img")
        card.append(pic)

        if item.get("poster"):
            load_texture_async(item["poster"], lambda tex: pic.set_paintable(tex))

        # Badge row: Type + Year
        b_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        badge = Gtk.Label(label="🎬 Movie" if item["type"] == "movie" else "📺 TV Show")
        badge.add_css_class("badge-movie" if item["type"] == "movie" else "badge-tv")
        b_row.append(badge)

        y_lbl = Gtk.Label(label=str(item.get("year", "")))
        y_lbl.add_css_class("hero-time")
        b_row.append(y_lbl)
        card.append(b_row)

        # Title
        title_lbl = Gtk.Label(label=item["title"])
        title_lbl.set_halign(Gtk.Align.START)
        title_lbl.set_wrap(True)
        title_lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        title_lbl.set_lines(2)
        title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        title_lbl.add_css_class("media-card-title")
        card.append(title_lbl)

        # Dual Action Buttons directly on card
        action_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        play_btn = Gtk.Button()
        play_btn.add_css_class("btn-play")
        play_btn.set_tooltip_text("Play Locally (MPV)")
        pb_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        pb_box.append(Gtk.Image.new_from_icon_name("media-playback-start-symbolic"))
        pb_box.append(Gtk.Label(label="Play"))
        play_btn.set_child(pb_box)
        play_btn.connect("clicked", lambda b, it=item: self._on_quick_pick_clicked(it, force_local=True))
        action_row.append(play_btn)

        cast_btn = Gtk.Button()
        cast_btn.add_css_class("btn-cast")
        cast_btn.set_tooltip_text("Cast to TV")
        cb_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        cb_box.append(Gtk.Image.new_from_icon_name("tv-symbolic"))
        cb_box.append(Gtk.Label(label="Cast"))
        cast_btn.set_child(cb_box)
        cast_btn.connect("clicked", lambda b, it=item: self._on_quick_pick_clicked(it, force_local=False))
        action_row.append(cast_btn)

        card.append(action_row)

        # Click card to view episodes/details
        gesture = Gtk.GestureClick.new()
        gesture.connect("released", lambda g, n, x, y, it=item: self._on_load_movie_details(it))
        card.add_controller(gesture)

        return card

    # Movies Details / TV Episodes Page
    def _create_movies_details_page(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(880)
        clamp.set_tightening_threshold(660)

        self.movies_details_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.movies_details_box.set_margin_top(14)
        self.movies_details_box.set_margin_bottom(20)
        self.movies_details_box.set_margin_start(16)
        self.movies_details_box.set_margin_end(16)

        self.movies_detail_header = Adw.Bin()
        self.movies_detail_header.add_css_class("card")
        self.movies_details_box.append(self.movies_detail_header)

        # TV Show Season selector row
        self.tv_season_scroll = Gtk.ScrolledWindow()
        self.tv_season_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.tv_season_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.tv_season_scroll.set_child(self.tv_season_box)
        self.movies_details_box.append(self.tv_season_scroll)

        # TV Show Episodes group
        self.tv_episodes_group = Adw.PreferencesGroup()
        self.tv_episodes_group.set_title("Episodes")
        self.movies_details_box.append(self.tv_episodes_group)

        clamp.set_child(self.movies_details_box)
        scrolled.set_child(clamp)
        return scrolled

    def _on_load_movie_details(self, item):
        self.current_movie_item = item
        self.back_btn.set_visible(True)
        self.movies_substack.set_visible_child_name("movies_details")

        h_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        h_box.set_margin_top(12)
        h_box.set_margin_bottom(12)
        h_box.set_margin_start(14)
        h_box.set_margin_end(14)

        ep_poster = Gtk.Picture()
        ep_poster.set_size_request(85, 120)
        ep_poster.set_content_fit(Gtk.ContentFit.COVER)
        ep_poster.add_css_class("poster-img")
        h_box.append(ep_poster)

        if item.get("poster"):
            load_texture_async(item["poster"], lambda tex: ep_poster.set_paintable(tex))

        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        right_box.set_hexpand(True)

        m_title = Gtk.Label(label=item["title"])
        m_title.add_css_class("title-3")
        m_title.set_halign(Gtk.Align.START)
        m_title.set_wrap(True)
        m_title.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        right_box.append(m_title)

        info_lbl = Gtk.Label(label=f"{item.get('year', '')} • {'Movie' if item['type'] == 'movie' else 'TV Series'} • {item.get('cast', '')}")
        info_lbl.add_css_class("hero-subtitle")
        info_lbl.set_halign(Gtk.Align.START)
        right_box.append(info_lbl)

        # Dual Actions: Play Local, Cast
        actions_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        play_btn = Gtk.Button()
        play_btn.add_css_class("suggested-action")
        play_btn.add_css_class("pill")
        ps_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        ps_box.append(Gtk.Image.new_from_icon_name("media-playback-start-symbolic"))
        ps_box.append(Gtk.Label(label="Play (Local MPV)"))
        play_btn.set_child(ps_box)
        play_btn.connect("clicked", lambda b, it=item: self._on_quick_pick_clicked(it, force_local=True))
        actions_row.append(play_btn)

        cast_btn = Gtk.Button()
        cast_btn.add_css_class("pill")
        cs_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        cs_box.append(Gtk.Image.new_from_icon_name("tv-symbolic"))
        cs_box.append(Gtk.Label(label="Cast to TV"))
        cast_btn.set_child(cs_box)
        cast_btn.connect("clicked", lambda b, it=item: self._on_quick_pick_clicked(it, force_local=False))
        actions_row.append(cast_btn)

        right_box.append(actions_row)
        h_box.append(right_box)
        self.movies_detail_header.set_child(h_box)

        # If TV Show: fetch seasons and episodes
        if item["type"] == "tv":
            self.tv_season_scroll.set_visible(True)
            self.tv_episodes_group.set_visible(True)

            def _fetch():
                seasons = movies_engine.get_tv_seasons_and_episodes(item["id"], item["title"])
                GLib.idle_add(self._display_tv_seasons_and_episodes, seasons)

            threading.Thread(target=_fetch, daemon=True).start()
        else:
            self.tv_season_scroll.set_visible(False)
            self.tv_episodes_group.set_visible(False)

    def _display_tv_seasons_and_episodes(self, seasons_dict):
        self.movie_seasons_dict = seasons_dict
        clear_container(self.tv_season_box)

        available_seasons = sorted(seasons_dict.keys())
        if not available_seasons:
            return

        lbl = Gtk.Label(label="Seasons:")
        lbl.add_css_class("heading")
        self.tv_season_box.append(lbl)

        for s_num in available_seasons:
            s_btn = Gtk.Button(label=f"Season {s_num}")
            if s_num == self.current_movie_season_num:
                s_btn.add_css_class("suggested-action")
            s_btn.connect("clicked", lambda b, sn=s_num: self._on_tv_season_btn_clicked(sn))
            self.tv_season_box.append(s_btn)

        self._populate_tv_episodes(self.current_movie_season_num)

    def _on_tv_season_btn_clicked(self, s_num):
        self.current_movie_season_num = s_num
        self._display_tv_seasons_and_episodes(self.movie_seasons_dict)

    def _populate_tv_episodes(self, s_num):
        # Clear existing rows safely
        for r in self.tv_episode_rows:
            try:
                self.tv_episodes_group.remove(r)
            except Exception:
                pass
        self.tv_episode_rows.clear()

        episodes = self.movie_seasons_dict.get(s_num, [])
        self.tv_episodes_group.set_title(f"Season {s_num} Episodes ({len(episodes)} total)")

        for ep in episodes:
            row = Adw.ActionRow()
            ep_num = ep["number"]
            row.set_title(f"Episode {ep_num}: {ep['title']}")
            if ep.get("airdate"):
                row.set_subtitle(f"Aired: {ep['airdate']}")

            # Dual Actions: Play Local, Cast
            p_btn = Gtk.Button(icon_name="media-playback-start-symbolic")
            p_btn.add_css_class("flat")
            p_btn.set_tooltip_text("Play Locally (MPV)")
            p_btn.connect("clicked", lambda b, e=ep: self._on_play_tv_episode(s_num, e["number"], force_local=True))
            row.add_suffix(p_btn)

            c_btn = Gtk.Button(icon_name="tv-symbolic")
            c_btn.add_css_class("flat")
            c_btn.set_tooltip_text("Cast to TV")
            c_btn.connect("clicked", lambda b, e=ep: self._on_play_tv_episode(s_num, e["number"], force_local=False))
            row.add_suffix(c_btn)

            row.set_activatable(True)
            gesture = Gtk.GestureClick.new()
            gesture.connect("released", lambda g, n, x, y, e=ep: self._on_play_tv_episode(s_num, e["number"], force_local=True))
            row.add_controller(gesture)

            self.tv_episode_rows.append(row)
            self.tv_episodes_group.add(row)

    def _on_play_tv_episode(self, season_num, episode_num, force_local=True):
        dev = {"name": "This Device (Local Screen / MPV)", "id": "local", "ip": "127.0.0.1", "is_local": True} if force_local else self.device_mgr.get_selected_device()
        self.playback_mgr.play_tv_show(
            self.current_movie_item["id"],
            season_num,
            episode_num,
            self.current_movie_item["title"],
            target_device=dev,
        )

    # =========================================================================
    # TAB 3: 💾 DOWNLOADS / LOCAL LIBRARY
    # =========================================================================
    def _create_library_tab(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(880)
        clamp.set_tightening_threshold(660)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.set_margin_top(14)
        box.set_margin_bottom(20)
        box.set_margin_start(16)
        box.set_margin_end(16)

        # Top banner with quick buttons
        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        lib_title = Gtk.Label(label="💾 Local Downloads & Library")
        lib_title.add_css_class("title-3")
        lib_title.set_halign(Gtk.Align.START)
        lib_title.set_hexpand(True)
        top_row.append(lib_title)

        refresh_btn = Gtk.Button(label="Refresh")
        refresh_btn.set_icon_name("view-refresh-symbolic")
        refresh_btn.connect("clicked", lambda b: self.refresh_local_library())
        top_row.append(refresh_btn)

        folder_btn = Gtk.Button(label="Open Folder")
        folder_btn.set_icon_name("folder-symbolic")
        folder_btn.connect("clicked", self._on_open_videos_folder)
        top_row.append(folder_btn)

        box.append(top_row)

        # Local library preferences group
        self.library_group = Adw.PreferencesGroup()
        self.library_group.set_title("Downloaded Media Files")
        box.append(self.library_group)

        self.library_empty_lbl = Gtk.Label(label="No downloaded media files found in ~/Videos/Anime or ~/Videos/Movies.")
        self.library_empty_lbl.set_margin_top(20)
        self.library_empty_lbl.set_visible(False)
        box.append(self.library_empty_lbl)

        clamp.set_child(box)
        scrolled.set_child(clamp)
        return scrolled

    def refresh_local_library(self):
        for r in self.library_rows:
            try:
                self.library_group.remove(r)
            except Exception:
                pass
        self.library_rows.clear()

        files = scan_local_library()
        if not files:
            self.library_empty_lbl.set_visible(True)
            return

        self.library_empty_lbl.set_visible(False)
        for item in files:
            row = Adw.ActionRow()
            row.set_title(item["title"])
            row.set_subtitle(f"{item['size_str']} • {item['filename']}")

            # Dual Action Buttons: Play Local, Cast to TV
            p_btn = Gtk.Button(icon_name="media-playback-start-symbolic")
            p_btn.add_css_class("flat")
            p_btn.set_tooltip_text("Play Locally (MPV)")
            p_btn.connect("clicked", lambda b, it=item: self._on_play_local_file(it["path"], it["title"], force_local=True))
            row.add_suffix(p_btn)

            c_btn = Gtk.Button(icon_name="tv-symbolic")
            c_btn.add_css_class("flat")
            c_btn.set_tooltip_text("Cast to TV")
            c_btn.connect("clicked", lambda b, it=item: self._on_play_local_file(it["path"], it["title"], force_local=False))
            row.add_suffix(c_btn)

            row.set_activatable(True)
            gesture = Gtk.GestureClick.new()
            gesture.connect("released", lambda g, n, x, y, it=item: self._on_play_local_file(it["path"], it["title"], force_local=True))
            row.add_controller(gesture)

            self.library_rows.append(row)
            self.library_group.add(row)

    def _on_play_local_file(self, file_path, title, force_local=True):
        dev = {"name": "This Device (Local Screen / MPV)", "id": "local", "ip": "127.0.0.1", "is_local": True} if force_local else self.device_mgr.get_selected_device()
        self.playback_mgr.play_local_file(file_path, title=title, target_device=dev)

    def _on_open_videos_folder(self, btn):
        target_dir = BASE_ANIME_DIR if os.path.exists(BASE_ANIME_DIR) else os.path.expanduser("~/Videos")
        subprocess.Popen(["xdg-open", target_dir])

    # =========================================================================
    # Navigation Back Handler
    # =========================================================================
    def _on_back_clicked(self, btn):
        current_tab = self.main_view_stack.get_visible_child_name()
        if current_tab == "anime":
            sub_page = self.anime_substack.get_visible_child_name()
            if sub_page == "anime_episodes":
                self.anime_substack.set_visible_child_name("anime_search" if self.anime_search_entry.get_text() else "anime_home")
                if self.anime_substack.get_visible_child_name() == "anime_home":
                    self.back_btn.set_visible(False)
                    self.refresh_anime_continue_watching()
            elif sub_page == "anime_search":
                self.anime_substack.set_visible_child_name("anime_home")
                self.back_btn.set_visible(False)
                self.refresh_anime_continue_watching()
        elif current_tab == "movies":
            sub_page = self.movies_substack.get_visible_child_name()
            if sub_page == "movies_details":
                self.movies_substack.set_visible_child_name("movies_search" if self.movies_search_entry.get_text() else "movies_home")
                if self.movies_substack.get_visible_child_name() == "movies_home":
                    self.back_btn.set_visible(False)
            elif sub_page == "movies_search":
                self.movies_substack.set_visible_child_name("movies_home")
                self.back_btn.set_visible(False)

    # =========================================================================
    # Playback Callbacks & Toast Notifications
    # =========================================================================
    def _on_playback_status_change(self, status, detail):
        if status == "playing":
            self.stop_btn.set_visible(True)
            self.show_toast(f"Playing {detail}")
        elif status == "loading":
            self.show_toast(f"Loading stream: {detail}...")
        elif status == "stopped":
            self.stop_btn.set_visible(False)
            self.refresh_anime_continue_watching()
            self.refresh_local_library()
        elif status == "error":
            self.stop_btn.set_visible(False)
            self.show_toast(f"Playback error: {detail}")

    def _on_auto_advance(self, anime_title, season_num, episode_num, _ep_id):
        self.show_toast(f"Auto-advancing: Season {season_num} Episode {episode_num}")
        self.refresh_anime_continue_watching()

    def show_toast(self, text):
        toast = Adw.Toast.new(text)
        toast.set_timeout(3)
        self.toast_overlay.add_toast(toast)


AniCastWindow = OmniViewWindow
