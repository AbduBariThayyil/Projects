"""
Main entry point for Ant Esports GM320 Gaming Mouse Master Control.
"""

import argparse
import os
import shlex
import signal
import subprocess
import sys

# Ensure package root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from ant_gm320.ui.main_window import MainWindow

ASSET_ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "mouse_transparent.png")
UDEV_RULE = 'SUBSYSTEM=="hidraw", ATTRS{idVendor}=="30fa", MODE="0666", TAG+="uaccess"'
UDEV_RULE_PATH = "/etc/udev/rules.d/99-ant-gm320.rules"


def print_udev_rule() -> None:
    """Print the standard udev rule for Ant Esports GM320."""
    print(UDEV_RULE)


def install_udev_rule() -> int:
    """Install the udev rule to /etc/udev/rules.d/99-ant-gm320.rules."""
    print(f"Installing udev rule to {UDEV_RULE_PATH}...")
    try:
        with open(UDEV_RULE_PATH, "w") as f:
            f.write(UDEV_RULE + "\n")
        subprocess.run(["udevadm", "control", "--reload-rules"], check=False)
        subprocess.run(["udevadm", "trigger"], check=False)
        print(f"✓ Successfully installed {UDEV_RULE_PATH} and reloaded udev rules.")
        return 0
    except PermissionError:
        print("Root permissions required to write to /etc/udev/rules.d/.")
        print("Attempting with sudo...")
        try:
            cmd = (
                f"echo {shlex.quote(UDEV_RULE)} | sudo tee {UDEV_RULE_PATH} > /dev/null "
                f"&& sudo udevadm control --reload-rules && sudo udevadm trigger"
            )
            res = subprocess.run(cmd, shell=True)
            if res.returncode == 0:
                print(f"✓ Successfully installed {UDEV_RULE_PATH} with sudo.")
                return 0
            else:
                print(f"Failed to write to {UDEV_RULE_PATH}.")
                print(
                    f"Please run manually:\n"
                    f"  echo '{UDEV_RULE}' | sudo tee {UDEV_RULE_PATH}\n"
                    f"  sudo udevadm control --reload-rules && sudo udevadm trigger"
                )
                return 1
        except Exception as exc:
            print(f"Error during sudo install: {exc}")
            return 1
    except Exception as exc:
        print(f"Error writing udev rule: {exc}")
        return 1


def main(argv=None) -> int:
    """Application main entrypoint."""
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        description="Ant Esports GM320 Gaming Mouse Master Control"
    )
    parser.add_argument(
        "--udev",
        action="store_true",
        help="Print the standard udev rule for Ant Esports GM320",
    )
    parser.add_argument(
        "--install-udev",
        action="store_true",
        help="Install the udev rule to /etc/udev/rules.d/99-ant-gm320.rules",
    )
    args, qt_args = parser.parse_known_args(argv)

    if args.udev:
        print_udev_rule()
        return 0

    if args.install_udev:
        return install_udev_rule()

    # Enable High DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication([sys.argv[0]] + qt_args)
    app.setApplicationName("Ant Esports GM320 Master Control")
    app.setOrganizationName("AntEsportsLinux")

    if os.path.exists(ASSET_ICON_PATH):
        app.setWindowIcon(QIcon(ASSET_ICON_PATH))

    window = MainWindow()

    def handle_signal(signum, frame):
        """Cleanly handle termination signals and close Qt application."""
        if window:
            window.close()
        app.quit()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Periodic timer to allow Python signal handlers to run while Qt event loop executes
    sig_timer = QTimer()
    sig_timer.timeout.connect(lambda: None)
    sig_timer.start(250)

    # Clean shutdown on aboutToQuit
    app.aboutToQuit.connect(window.close)

    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
