"""
Inbuilt Video Player View for OmniView.
Embeds native MPV via an X11 child subwindow inside GTK 4 / Libadwaita.
Provides full on-screen controls:
- Top Bar: Back, Media Title, Cast to TV, Fullscreen toggle
- Video Canvas: Dynamic X11 child subwindow allocation and resize tracking
- Bottom Bar: Scrub Slider, Play/Pause, Next/Prev episode, Volume, Time, Quality & Sub badges
- Keyboard shortcuts: Space, Arrows, F, Escape
"""
import os
import sys
import ctypes
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("GLib", "2.0")

from gi.repository import Gtk, Gdk, GLib, Pango

# Load libX11
try:
    libx11 = ctypes.CDLL("libX11.so.6")

    libx11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    libx11.XOpenDisplay.restype = ctypes.c_void_p

    libx11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    libx11.XCloseDisplay.restype = ctypes.c_int

    libx11.XCreateWindow.argtypes = [
        ctypes.c_void_p, ctypes.c_ulong,
        ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint,
        ctypes.c_uint, ctypes.c_int, ctypes.c_uint, ctypes.c_void_p,
        ctypes.c_ulong, ctypes.c_void_p,
    ]
    libx11.XCreateWindow.restype = ctypes.c_ulong

    libx11.XMapWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    libx11.XMapWindow.restype = ctypes.c_int

    libx11.XUnmapWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    libx11.XUnmapWindow.restype = ctypes.c_int

    libx11.XDestroyWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    libx11.XDestroyWindow.restype = ctypes.c_int

    libx11.XMoveResizeWindow.argtypes = [
        ctypes.c_void_p, ctypes.c_ulong,
        ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint,
    ]
    libx11.XMoveResizeWindow.restype = ctypes.c_int

    libx11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
    libx11.XSync.restype = ctypes.c_int
except Exception as e:
    libx11 = None
    print(f"[PlayerView] Warning: libX11 could not be loaded: {e}", file=sys.stderr)


def format_seconds(seconds: float) -> str:
    if seconds is None or seconds < 0:
        return "00:00"
    s = int(seconds)
    hours = s // 3600
    minutes = (s % 3600) // 60
    secs = s % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


class VideoCanvas(Gtk.Widget):
    """
    Dedicated GTK4 widget representing the video rendering canvas.
    Tracks exact geometry bounds relative to toplevel surface and resizes
    the underlying child X11 subwindow so MPV renders perfectly.
    """
    __gtype_name__ = "OmniViewVideoCanvas"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.dpy = None
        self.child_xid = None
        self.parent_xid = None
        self.last_bounds = (0, 0, 0, 0)

    def attach_x11(self, parent_xid: int) -> int:
        """Creates and maps an X11 child subwindow under parent_xid."""
        if not libx11:
            return 0

        self.cleanup_x11()

        try:
            self.parent_xid = parent_xid
            self.dpy = libx11.XOpenDisplay(None)
            if not self.dpy:
                return 0

            # Determine initial bounds
            root = self.get_root()
            x, y, w, h = 0, 0, 640, 480
            if root:
                ok, b = self.compute_bounds(root)
                if ok:
                    x = max(0, int(b.get_x()))
                    y = max(0, int(b.get_y()))
                    w = max(1, int(b.get_width()))
                    h = max(1, int(b.get_height()))

            # InputOutput = 1
            self.child_xid = libx11.XCreateWindow(
                self.dpy,
                self.parent_xid,
                x, y, w, h,
                0, 0, 1,
                None, 0, None,
            )
            libx11.XMapWindow(self.dpy, self.child_xid)
            libx11.XSync(self.dpy, 0)
            self.last_bounds = (x, y, w, h)
            return self.child_xid
        except Exception as e:
            print(f"[VideoCanvas] Error attaching X11 child: {e}", file=sys.stderr)
            return 0

    def sync_geometry(self):
        """Forces geometry sync with current widget bounds."""
        if not (self.dpy and self.child_xid and libx11):
            return
        root = self.get_root()
        if not root:
            return
        ok, b = self.compute_bounds(root)
        if ok:
            x = max(0, int(b.get_x()))
            y = max(0, int(b.get_y()))
            w = max(1, int(b.get_width()))
            h = max(1, int(b.get_height()))
            if (x, y, w, h) != self.last_bounds:
                self.last_bounds = (x, y, w, h)
                libx11.XMoveResizeWindow(self.dpy, self.child_xid, x, y, w, h)
                libx11.XSync(self.dpy, 0)

    def do_size_allocate(self, width, height, baseline):
        self.sync_geometry()

    def cleanup_x11(self):
        """Destroys the X11 child subwindow cleanly."""
        if not libx11:
            return
        if self.child_xid and self.dpy:
            try:
                libx11.XUnmapWindow(self.dpy, self.child_xid)
                libx11.XDestroyWindow(self.dpy, self.child_xid)
                libx11.XSync(self.dpy, 0)
            except Exception:
                pass
            self.child_xid = None

        if self.dpy:
            try:
                libx11.XCloseDisplay(self.dpy)
            except Exception:
                pass
            self.dpy = None
        self.last_bounds = (0, 0, 0, 0)


class PlayerView(Gtk.Box):
    """
    Complete Inbuilt Player View with native Top Bar, embedded Video Canvas,
    and Bottom Bar controls.
    """
    def __init__(
        self,
        playback_mgr,
        on_back=None,
        on_cast=None,
        on_fullscreen=None,
        on_prev=None,
        on_next=None,
        **kwargs,
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kwargs)
        self.playback_mgr = playback_mgr
        self.on_back_callback = on_back
        self.on_cast_callback = on_cast
        self.on_fullscreen_callback = on_fullscreen
        self.on_prev_callback = on_prev
        self.on_next_callback = on_next

        self.add_css_class("player-view")
        self.set_hexpand(True)
        self.set_vexpand(True)

        self._is_seeking = False
        self._updating_slider = False
        self._is_fullscreen = False
        self._duration = 0.0

        # Build subcomponents
        self._build_top_bar()
        self._build_video_area()
        self._build_bottom_bar()
        self._setup_key_controller()

    def _build_top_bar(self):
        self.top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.top_bar.add_css_class("player-top-bar")
        self.top_bar.set_size_request(-1, 46)

        # 1. Back button
        self.back_btn = Gtk.Button()
        self.back_btn.add_css_class("pill")
        self.back_btn.add_css_class("flat")
        self.back_btn.set_tooltip_text("Exit Player (Esc)")
        b_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        b_box.append(Gtk.Image.new_from_icon_name("go-previous-symbolic"))
        b_box.append(Gtk.Label(label="Back"))
        self.back_btn.set_child(b_box)
        self.back_btn.connect("clicked", self._on_back_clicked)
        self.top_bar.append(self.back_btn)

        # 2. Centered Title box
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title_box.set_hexpand(True)
        title_box.set_valign(Gtk.Align.CENTER)

        self.title_label = Gtk.Label(label="OmniView Player")
        self.title_label.add_css_class("heading")
        self.title_label.add_css_class("player-title")
        self.title_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.title_label.set_halign(Gtk.Align.CENTER)

        self.subtitle_label = Gtk.Label(label="")
        self.subtitle_label.add_css_class("dim-label")
        self.subtitle_label.add_css_class("player-subtitle")
        self.subtitle_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.subtitle_label.set_halign(Gtk.Align.CENTER)
        self.subtitle_label.set_visible(False)

        title_box.append(self.title_label)
        title_box.append(self.subtitle_label)
        self.top_bar.append(title_box)

        # 3. Cast to TV button
        self.cast_btn = Gtk.Button()
        self.cast_btn.add_css_class("pill")
        self.cast_btn.add_css_class("flat")
        self.cast_btn.set_tooltip_text("Cast Stream to TV")
        c_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        c_box.append(Gtk.Image.new_from_icon_name("tv-symbolic"))
        c_box.append(Gtk.Label(label="Cast"))
        self.cast_btn.set_child(c_box)
        self.cast_btn.connect("clicked", self._on_cast_clicked)
        self.top_bar.append(self.cast_btn)

        # 4. Fullscreen button
        self.fs_btn = Gtk.Button(icon_name="view-fullscreen-symbolic")
        self.fs_btn.add_css_class("pill")
        self.fs_btn.add_css_class("flat")
        self.fs_btn.set_tooltip_text("Toggle Fullscreen (F)")
        self.fs_btn.connect("clicked", self._on_fs_clicked)
        self.top_bar.append(self.fs_btn)

        self.append(self.top_bar)

    def _build_video_area(self):
        self.video_overlay = Gtk.Overlay()
        self.video_overlay.set_hexpand(True)
        self.video_overlay.set_vexpand(True)
        self.video_overlay.add_css_class("player-canvas-area")

        # Native Video Canvas
        self.video_canvas = VideoCanvas()
        self.video_overlay.set_child(self.video_canvas)

        # Loading Spinner Overlay
        self.loading_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.loading_box.add_css_class("player-loading-overlay")
        self.loading_box.set_halign(Gtk.Align.CENTER)
        self.loading_box.set_valign(Gtk.Align.CENTER)

        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(48, 48)
        self.loading_box.append(self.spinner)

        self.loading_status = Gtk.Label(label="Loading stream...")
        self.loading_status.add_css_class("title-3")
        self.loading_box.append(self.loading_status)

        self.loading_detail = Gtk.Label(label="Resolving stream sources...")
        self.loading_detail.add_css_class("dim-label")
        self.loading_box.append(self.loading_detail)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.add_css_class("pill")
        cancel_btn.add_css_class("destructive-action")
        cancel_btn.connect("clicked", self._on_back_clicked)
        self.loading_box.append(cancel_btn)

        self.video_overlay.add_overlay(self.loading_box)
        self.append(self.video_overlay)

    def _build_bottom_bar(self):
        self.bottom_bar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.bottom_bar.add_css_class("player-bottom-bar")

        # Row 1: Scrub Scale + Time Label
        timeline_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        timeline_row.set_margin_start(14)
        timeline_row.set_margin_end(14)

        self.time_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.0, 100.0, 1.0)
        self.time_slider.set_hexpand(True)
        self.time_slider.add_css_class("player-scrub-scale")
        self.time_slider.set_draw_value(False)
        self.time_slider.connect("change-value", self._on_time_slider_change)

        # Detect user drag release
        drag = Gtk.GestureDrag.new()
        drag.connect("drag-begin", lambda g, x, y: setattr(self, "_is_seeking", True))
        drag.connect("drag-end", self._on_drag_end)
        self.time_slider.add_controller(drag)

        self.time_label = Gtk.Label(label="00:00 / 00:00")
        self.time_label.add_css_class("player-time-label")
        self.time_label.set_width_chars(13)
        self.time_label.set_halign(Gtk.Align.END)

        timeline_row.append(self.time_slider)
        timeline_row.append(self.time_label)
        self.bottom_bar.append(timeline_row)

        # Row 2: Control Buttons, Volume, Badges
        ctrl_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        ctrl_row.set_margin_start(14)
        ctrl_row.set_margin_end(14)
        ctrl_row.set_margin_bottom(6)

        # Prev Episode
        self.prev_btn = Gtk.Button(icon_name="media-skip-backward-symbolic")
        self.prev_btn.add_css_class("flat")
        self.prev_btn.add_css_class("circular")
        self.prev_btn.set_tooltip_text("Previous Episode")
        self.prev_btn.connect("clicked", lambda b: self.on_prev_callback() if self.on_prev_callback else None)
        ctrl_row.append(self.prev_btn)

        # Seek -10s
        self.rwd_btn = Gtk.Button(icon_name="media-seek-backward-symbolic")
        self.rwd_btn.add_css_class("flat")
        self.rwd_btn.add_css_class("circular")
        self.rwd_btn.set_tooltip_text("Seek -10s (Left Arrow)")
        self.rwd_btn.connect("clicked", lambda b: self.playback_mgr.seek(-10, relative=True))
        ctrl_row.append(self.rwd_btn)

        # Play / Pause Toggle
        self.play_btn = Gtk.Button(icon_name="media-playback-start-symbolic")
        self.play_btn.add_css_class("suggested-action")
        self.play_btn.add_css_class("circular")
        self.play_btn.add_css_class("player-play-btn")
        self.play_btn.set_tooltip_text("Play / Pause (Space)")
        self.play_btn.connect("clicked", self._on_play_toggle_clicked)
        ctrl_row.append(self.play_btn)

        # Seek +10s
        self.fwd_btn = Gtk.Button(icon_name="media-seek-forward-symbolic")
        self.fwd_btn.add_css_class("flat")
        self.fwd_btn.add_css_class("circular")
        self.fwd_btn.set_tooltip_text("Seek +10s (Right Arrow)")
        self.fwd_btn.connect("clicked", lambda b: self.playback_mgr.seek(10, relative=True))
        ctrl_row.append(self.fwd_btn)

        # Next Episode
        self.next_btn = Gtk.Button(icon_name="media-skip-forward-symbolic")
        self.next_btn.add_css_class("flat")
        self.next_btn.add_css_class("circular")
        self.next_btn.set_tooltip_text("Next Episode")
        self.next_btn.connect("clicked", lambda b: self.on_next_callback() if self.on_next_callback else None)
        ctrl_row.append(self.next_btn)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        ctrl_row.append(spacer)

        # Volume Controls
        self.vol_icon = Gtk.Image.new_from_icon_name("audio-volume-high-symbolic")
        ctrl_row.append(self.vol_icon)

        self.vol_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.0, 100.0, 5.0)
        self.vol_slider.set_size_request(100, -1)
        self.vol_slider.set_draw_value(False)
        self.vol_slider.set_value(100.0)
        self.vol_slider.set_tooltip_text("Volume (Up/Down)")
        self.vol_slider.connect("value-changed", self._on_volume_changed)
        ctrl_row.append(self.vol_slider)

        # Badges (Quality & Sub/Dub)
        self.quality_badge = Gtk.Label(label="1080p")
        self.quality_badge.add_css_class("badge-quality")
        ctrl_row.append(self.quality_badge)

        self.mode_badge = Gtk.Label(label="SUB")
        self.mode_badge.add_css_class("badge-audio")
        ctrl_row.append(self.mode_badge)

        self.append(self.bottom_bar)

    def _setup_key_controller(self):
        controller = Gtk.EventControllerKey.new()
        controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(controller)

    def _on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_space:
            self.playback_mgr.toggle_pause()
            return True
        elif keyval in [Gdk.KEY_Left, Gdk.KEY_h]:
            self.playback_mgr.seek(-5, relative=True)
            return True
        elif keyval in [Gdk.KEY_Right, Gdk.KEY_l]:
            self.playback_mgr.seek(5, relative=True)
            return True
        elif keyval in [Gdk.KEY_Up, Gdk.KEY_k]:
            self.playback_mgr.adjust_volume(5)
            new_vol = min(100.0, self.vol_slider.get_value() + 5.0)
            self.vol_slider.set_value(new_vol)
            return True
        elif keyval in [Gdk.KEY_Down, Gdk.KEY_j]:
            self.playback_mgr.adjust_volume(-5)
            new_vol = max(0.0, self.vol_slider.get_value() - 5.0)
            self.vol_slider.set_value(new_vol)
            return True
        elif keyval in [Gdk.KEY_f, Gdk.KEY_F]:
            self._on_fs_clicked(None)
            return True
        elif keyval == Gdk.KEY_Escape:
            if self._is_fullscreen:
                self._on_fs_clicked(None)
            else:
                self._on_back_clicked(None)
            return True
        return False

    def prepare_playback(self, title: str, subtitle: str = "", quality: str = "1080p", mode: str = "sub"):
        """Prepares UI state for an upcoming video stream."""
        self.title_label.set_label(title)
        if subtitle:
            self.subtitle_label.set_label(subtitle)
            self.subtitle_label.set_visible(True)
        else:
            self.subtitle_label.set_visible(False)

        self.quality_badge.set_label(quality.upper())
        self.mode_badge.set_label(mode.upper())

        self.time_slider.set_value(0.0)
        self.time_label.set_label("00:00 / 00:00")
        self.play_btn.set_icon_name("media-playback-start-symbolic")

        # Show loading indicator
        self.loading_status.set_label("Loading stream...")
        self.loading_detail.set_label(title)
        self.spinner.start()
        self.loading_box.set_visible(True)

    def attach_x11_surface(self, parent_xid: int) -> int:
        """Creates child X11 window on canvas."""
        return self.video_canvas.attach_x11(parent_xid)

    def get_child_xid(self) -> int:
        return self.video_canvas.child_xid or 0

    def on_playback_started(self):
        """Called when stream begins rendering in MPV."""
        self.spinner.stop()
        self.loading_box.set_visible(False)
        self.play_btn.set_icon_name("media-playback-pause-symbolic")
        self.video_canvas.sync_geometry()

    def on_progress(self, time_pos: float, duration: float):
        """Updates scrub slider and time label from MPV IPC."""
        if self._is_seeking:
            return

        self._updating_slider = True
        try:
            self._duration = duration
            if duration > 0:
                self.time_slider.set_range(0.0, duration)
            self.time_slider.set_value(time_pos)
            self.time_label.set_label(f"{format_seconds(time_pos)} / {format_seconds(duration)}")

            # If playback just started and loading overlay is still up:
            if time_pos > 0.1 and self.loading_box.get_visible():
                self.on_playback_started()
        finally:
            self._updating_slider = False

    def on_pause_change(self, is_paused: bool):
        icon = "media-playback-start-symbolic" if is_paused else "media-playback-pause-symbolic"
        self.play_btn.set_icon_name(icon)

    def on_playback_error(self, message: str):
        self.spinner.stop()
        self.loading_status.set_label("Playback Failed")
        self.loading_detail.set_label(message)

    def set_nav_buttons_state(self, has_prev: bool, has_next: bool):
        self.prev_btn.set_sensitive(has_prev)
        self.next_btn.set_sensitive(has_next)

    def set_fullscreen(self, is_fs: bool):
        self._is_fullscreen = is_fs
        icon = "view-restore-symbolic" if is_fs else "view-fullscreen-symbolic"
        self.fs_btn.set_icon_name(icon)
        self.video_canvas.sync_geometry()

    def _on_time_slider_change(self, scale, scroll_type, value):
        if not self._updating_slider and not self._is_seeking:
            self.playback_mgr.seek(value, relative=False)
        return False

    def _on_drag_end(self, gesture, offset_x, offset_y):
        self._is_seeking = False
        target_val = self.time_slider.get_value()
        self.playback_mgr.seek(target_val, relative=False)

    def _on_volume_changed(self, scale):
        vol = scale.get_value()
        self.playback_mgr.set_volume(vol)
        icon = "audio-volume-muted-symbolic" if vol < 1 else ("audio-volume-low-symbolic" if vol < 35 else ("audio-volume-medium-symbolic" if vol < 70 else "audio-volume-high-symbolic"))
        self.vol_icon.set_from_icon_name(icon)

    def _on_play_toggle_clicked(self, btn):
        self.playback_mgr.toggle_pause()

    def _on_back_clicked(self, btn):
        self.cleanup()
        if self.on_back_callback:
            self.on_back_callback()

    def _on_cast_clicked(self, btn):
        if self.on_cast_callback:
            self.on_cast_callback()

    def _on_fs_clicked(self, btn):
        if self.on_fullscreen_callback:
            self.on_fullscreen_callback()

    def cleanup(self):
        """Clean teardown: stops MPV and destroys X11 subwindow."""
        self.spinner.stop()
        self.loading_box.set_visible(False)
        self.playback_mgr.stop_playback()
        self.video_canvas.cleanup_x11()
