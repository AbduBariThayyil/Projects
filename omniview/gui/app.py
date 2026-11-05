"""
Adw.Application setup for OmniView Media Suite.
"""
import os
import sys

# Ensure GSK_RENDERER is cairo to prevent GL context crashes in bspwm / X11 environments
os.environ.setdefault("GSK_RENDERER", "cairo")
# Suppress a11y portal warnings if accessibility bus is disabled
os.environ.setdefault("GTK_A11Y", "none")

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gio", "2.0")

from gi.repository import Gtk, Adw, Gio, Gdk

from window import OmniViewWindow, AniCastWindow

APP_ID = "com.vibecoder.omniview"
CSS_PATH = os.path.join(os.path.dirname(__file__), "style.css")


class OmniViewApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.window = None

    def do_startup(self):
        Adw.Application.do_startup(self)

        # Prefer dark theme for media application (Catppuccin Mocha)
        style_mgr = Adw.StyleManager.get_default()
        style_mgr.set_color_scheme(Adw.ColorScheme.PREFER_DARK)

        # Load custom CSS
        if os.path.exists(CSS_PATH):
            provider = Gtk.CssProvider()
            provider.load_from_path(CSS_PATH)
            display = Gdk.Display.get_default()
            if display:
                Gtk.StyleContext.add_provider_for_display(
                    display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )

    def do_activate(self):
        if not self.window:
            self.window = OmniViewWindow(application=self)
        self.window.present()


AniCastApp = OmniViewApp


def main():
    app = OmniViewApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
