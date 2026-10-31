"""
Modern dark cyberpunk esports styling for Ant Esports GM320 application.
Features sleek dark cards, glowing electric blue and neon cyan accents,
clean typography, and custom Qt widget stylesheets.
"""

# Color Palette Constants
COLOR_BG_DARK = "#0d1117"
COLOR_BG_CARD = "#161b24"
COLOR_BG_CARD_HOVER = "#1c222e"
COLOR_BORDER = "#263040"
COLOR_BORDER_FOCUS = "#00e5ff"

COLOR_CYAN_NEON = "#00e5ff"
COLOR_BLUE_ACCENT = "#3a86ff"
COLOR_PURPLE_ACCENT = "#7928ca"
COLOR_PINK_ACCENT = "#ff007f"
COLOR_GREEN_SUCCESS = "#00f59b"
COLOR_RED_DANGER = "#ff3366"
COLOR_ORANGE_WARNING = "#ff9900"

COLOR_TEXT_PRIMARY = "#f0f6fc"
COLOR_TEXT_SECONDARY = "#8b949e"
COLOR_TEXT_MUTED = "#586069"

STYLE_SHEET = f"""
QMainWindow, QDialog {{
    background-color: {COLOR_BG_DARK};
    color: {COLOR_TEXT_PRIMARY};
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}}

QWidget {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 13px;
}}

/* Top Navigation Tabs */
QTabBar::tab {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    padding: 10px 24px;
    margin-right: 6px;
    font-weight: 600;
    font-size: 13px;
    border-bottom: 2px solid transparent;
    border-radius: 4px;
}}

QTabBar::tab:hover {{
    color: {COLOR_TEXT_PRIMARY};
    background-color: {COLOR_BG_CARD};
}}

QTabBar::tab:selected {{
    color: {COLOR_CYAN_NEON};
    border-bottom: 2px solid {COLOR_CYAN_NEON};
    background-color: rgba(0, 229, 255, 0.08);
}}

/* Cards & Groupboxes */
QGroupBox {{
    background-color: {COLOR_BG_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    margin-top: 24px;
    padding-top: 18px;
    font-weight: 600;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    top: 6px;
    color: {COLOR_CYAN_NEON};
    font-size: 12px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}}

/* Push Buttons */
QPushButton {{
    background-color: {COLOR_BG_CARD};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
}}

QPushButton:hover {{
    background-color: {COLOR_BG_CARD_HOVER};
    border-color: {COLOR_CYAN_NEON};
    color: #ffffff;
}}

QPushButton:pressed {{
    background-color: rgba(0, 229, 255, 0.15);
}}

QPushButton:disabled {{
    background-color: rgba(22, 27, 36, 0.5);
    border-color: #1e2530;
    color: {COLOR_TEXT_MUTED};
}}

QPushButton#primaryBtn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00b4d8, stop:1 #00e5ff);
    color: #050a12;
    border: none;
    font-weight: 700;
}}

QPushButton#primaryBtn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00c6eb, stop:1 #33ecff);
    border: none;
}}

QPushButton#dangerBtn {{
    background-color: rgba(255, 51, 102, 0.15);
    color: {COLOR_RED_DANGER};
    border: 1px solid rgba(255, 51, 102, 0.3);
}}

QPushButton#dangerBtn:hover {{
    background-color: rgba(255, 51, 102, 0.3);
    border-color: {COLOR_RED_DANGER};
}}

/* Sliders */
QSlider::groove:horizontal {{
    height: 6px;
    background: #1e2634;
    border-radius: 3px;
}}

QSlider::sub-page:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLOR_BLUE_ACCENT}, stop:1 {COLOR_CYAN_NEON});
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    background: #ffffff;
    border: 2px solid {COLOR_CYAN_NEON};
    width: 16px;
    margin-top: -6px;
    margin-bottom: -6px;
    border-radius: 8px;
}}

QSlider::handle:horizontal:hover {{
    background: {COLOR_CYAN_NEON};
    border-color: #ffffff;
}}

/* Combo Boxes */
QComboBox {{
    background-color: {COLOR_BG_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 6px 12px;
    color: {COLOR_TEXT_PRIMARY};
    min-height: 24px;
}}

QComboBox:hover, QComboBox:focus {{
    border-color: {COLOR_CYAN_NEON};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox::down-arrow {{
    width: 0px;
    height: 0px;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {COLOR_CYAN_NEON};
    margin-right: 10px;
}}

QComboBox QAbstractItemView {{
    background-color: #12161f;
    border: 1px solid {COLOR_BORDER};
    selection-background-color: rgba(0, 229, 255, 0.15);
    selection-color: {COLOR_CYAN_NEON};
    padding: 4px;
    border-radius: 6px;
}}

/* Checkboxes */
QCheckBox {{
    spacing: 8px;
    color: {COLOR_TEXT_PRIMARY};
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {COLOR_BORDER};
    border-radius: 4px;
    background: {COLOR_BG_CARD};
}}

QCheckBox::indicator:hover {{
    border-color: {COLOR_CYAN_NEON};
}}

QCheckBox::indicator:checked {{
    background-color: {COLOR_CYAN_NEON};
    border-color: {COLOR_CYAN_NEON};
    image: none;
}}

/* Radio Buttons */
QRadioButton {{
    spacing: 8px;
    color: {COLOR_TEXT_PRIMARY};
}}

QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {COLOR_BORDER};
    border-radius: 9px;
    background: {COLOR_BG_CARD};
}}

QRadioButton::indicator:checked {{
    border: 5px solid {COLOR_CYAN_NEON};
    background: #0d1117;
}}

/* SpinBoxes & Inputs */
QSpinBox, QLineEdit {{
    background-color: {COLOR_BG_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    color: {COLOR_TEXT_PRIMARY};
}}

QSpinBox:focus, QLineEdit:focus {{
    border-color: {COLOR_CYAN_NEON};
}}

/* Lists */
QListWidget {{
    background-color: #12161f;
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 4px;
}}

QListWidget::item {{
    padding: 8px 12px;
    border-radius: 4px;
    margin-bottom: 2px;
}}

QListWidget::item:hover {{
    background-color: {COLOR_BG_CARD};
}}

QListWidget::item:selected {{
    background-color: rgba(0, 229, 255, 0.15);
    color: {COLOR_CYAN_NEON};
    font-weight: 600;
}}

/* Scrollbars */
QScrollBar:vertical {{
    background: #0d1117;
    width: 8px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: #273142;
    min-height: 20px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: {COLOR_CYAN_NEON};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""
